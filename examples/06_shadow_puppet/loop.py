#!/usr/bin/env python3
"""Game flow: sit watch -> alert -> one screen per action -> summary -> back to watch."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from gestures import Motion

SAVE = Path(__file__).resolve().parent / "save.json"

# phases
AWAY = "away"
MONITOR = "monitor"
ALERT = "alert"
ROUND = "round"
SUMMARY = "summary"

# round sub-states
READY = "ready"
PLAY = "play"
CLEAR = "clear"

ACTS = (
    {
        "id": "wings",
        "scene": "wings",
        "name": "展翅",
        "en": "WINGS",
        "tip": "左右手臂都平举撑满，坚持住别被风吹散",
        "goal": "撑满两侧并坚持 5 秒",
        "kind": "hold",
        "need": 5.0,
    },
    {
        "id": "flap",
        "scene": "eagle",
        "name": "老鹰",
        "en": "EAGLE",
        "tip": "双臂向两侧平举成翅膀，再上下扇；放下就掉",
        "goal": "展翅扇动 8 次飞到旗子",
        "kind": "reps",
        "need": 8,
    },
    {
        "id": "wave",
        "scene": "wave",
        "name": "挥手",
        "en": "WAVE",
        "tip": "抬手左右挥，送走这一周",
        "goal": "挥手 10 次",
        "kind": "reps",
        "need": 10,
    },
    {
        "id": "lean",
        "scene": "ski",
        "name": "滑雪",
        "en": "SKI",
        "tip": "上身左右倒，碰旗子躲松树",
        "goal": "碰到 6 面旗",
        "kind": "reps",
        "need": 6,
    },
    {
        "id": "piano",
        "scene": "piano",
        "name": "弹琴",
        "en": "PIANO",
        "tip": "对准黄色高亮键，食指往下按一下",
        "goal": "按中 8 个黄键",
        "kind": "reps",
        "need": 8,
        "hands": True,
    },
    {
        "id": "hands_up",
        "scene": "dino",
        "name": "跳跃",
        "en": "JUMP",
        "tip": "坐着把身子往上颠一下跳过；不用挥翅膀",
        "goal": "跳过 5 个仙人掌",
        "kind": "reps",
        "need": 5,
    },
    {
        "id": "turn",
        "scene": "turn",
        "name": "转头",
        "en": "TURN",
        "tip": "左右各转头看一眼",
        "goal": "左右各 3 次",
        "kind": "reps",
        "need": 3,
    },
    {
        "id": "nod",
        "scene": "nod",
        "name": "点头",
        "en": "NOD",
        "tip": "轻轻上下点头就行，不用幅度很大",
        "goal": "点头 6 次",
        "kind": "reps",
        "need": 6,
    },
)

ACT_BY_ID = {a["id"]: a for a in ACTS}

LEVELS = ("工位菜鸟", "久坐战士", "回血学徒", "伸展骑士", "工位英雄")
GRADE_MUL = {"S": 2.0, "A": 1.6, "B": 1.3, "C": 1.0}

PRESENT_ON = 0.7
PRESENT_OFF = 40.0
WALK_SEC = 180.0
RESET_AWAY = 300.0
READY_T = 2.0
CLEAR_T = 1.7
ROUND_BUDGET = 120.0
SUMMARY_T = 13.0
NAG_EVERY = 90.0
VOLUNTARY_HOLD = 0.5
MOVE_ENERGY = 0.16
# bad posture alone empties HP in ~4 min; stacks with sit drain over interval
POSTURE_DRAIN_PER_S = 100.0 / 240.0
POSTURE_BAD_SCORE = 62.0


def mmss(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def grade_for(t: float) -> str:
    if t <= 8.0:
        return "S"
    if t <= 14.0:
        return "A"
    if t <= 22.0:
        return "B"
    return "C"


@dataclass
class ActResult:
    act: dict
    cleared: bool
    seconds: float
    grade: str
    points: int


@dataclass
class DeskGame:
    interval: float = 25 * 60
    round_len: int = 6
    phase: str = AWAY
    sub: str = READY
    present: bool = False
    seen_s: float = 0.0
    miss_s: float = 0.0
    away_s: float = 0.0
    sit_s: float = 0.0
    sit_day: float = 0.0
    hp_pool: float = 100.0  # sit + bad posture drain; reset after round
    score: int = 0
    combo: int = 0
    best_combo: int = 0
    rounds: int = 0
    streak: int = 0
    level_up: bool = False
    acts: list = field(default_factory=list)
    act_i: int = 0
    t_state: float = 0.0
    hold: float = 0.0
    peak: float = 0.0
    results: list = field(default_factory=list)
    round_score: int = 0
    round_time: float = 0.0
    trans: float = 0.0
    toast: str = ""
    toast_t: float = 0.0
    nag_t: float = 0.0
    energy_ema: float = 0.0
    early_hold: float = 0.0
    save_cd: float = 0.0
    rot: int = 0
    posture_avg: float = 100.0
    posture_n: int = 0
    posture_sum: float = 0.0
    round_posture: float = 100.0
    events: list = field(default_factory=list)
    path: Path = field(default_factory=lambda: SAVE)

    def __post_init__(self) -> None:
        self.load()

    def reset_day(self) -> None:
        self.sit_s = 0.0
        self.sit_day = 0.0
        self.hp_pool = 100.0
        self.rounds = 0
        self.streak = 0
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.phase = AWAY
        self.save()

    def _sit_drain_rate(self) -> float:
        return 100.0 / max(self.interval, 1.0)

    def _clamp_hp(self) -> None:
        self.hp_pool = float(max(0.0, min(100.0, self.hp_pool)))

    # ---------- derived ----------

    @property
    def act(self) -> dict:
        if self.acts and 0 <= self.act_i < len(self.acts):
            return self.acts[self.act_i]
        return ACTS[self.rot % len(ACTS)]

    @property
    def scene(self) -> str:
        return self.act["scene"]

    @property
    def done_n(self) -> int:
        return sum(1 for r in self.results if r.cleared)

    @property
    def round_left(self) -> float:
        return max(0.0, ROUND_BUDGET - self.round_time)

    @property
    def needs_hands(self) -> bool:
        return self.phase == ROUND and bool(self.act.get("hands"))

    @property
    def hp(self) -> int:
        if self.phase in (ROUND, SUMMARY):
            return int(20 + 80 * len(self.results) / max(self.round_len, 1))
        return int(max(0, round(self.hp_pool)))

    @property
    def overtime(self) -> float:
        return max(0.0, self.sit_s - self.interval)

    @property
    def remain(self) -> float:
        # ETA to empty HP at sit-only rate (bad posture makes alert sooner)
        return max(0.0, self.hp_pool / self._sit_drain_rate())

    @property
    def level(self) -> int:
        return min(len(LEVELS) - 1, self.score // 600)

    @property
    def title(self) -> str:
        return LEVELS[self.level]

    @property
    def posture_mean(self) -> float:
        return self.posture_sum / self.posture_n if self.posture_n else 100.0

    @property
    def posture_grade(self) -> str:
        s = self.posture_mean
        if s >= 88:
            return "S"
        if s >= 76:
            return "A"
        if s >= 62:
            return "B"
        return "C"

    def value(self, motion: Motion) -> float:
        return float(getattr(motion, self.act["id"], 0.0))

    def progress(self, motion: Motion) -> float:
        need = max(self.act["need"], 0.01)
        return min(1.0, self.value(motion) / need)

    def hold_frac(self) -> float:
        return min(1.0, self.hold / max(self.act["hold"], 0.01))

    def snapshot(self) -> dict:
        return {
            "phase": self.phase,
            "sub": self.sub if self.phase == ROUND else "",
            "present": self.present,
            "hp": self.hp,
            "sit_s": round(self.sit_s, 1),
            "remain_s": round(self.remain, 1),
            "sit_day": round(self.sit_day, 1),
            "interval": self.interval,
            "score": self.score,
            "combo": self.combo,
            "rounds": self.rounds,
            "streak": self.streak,
            "level": self.title,
            "act": self.act["name"] if self.phase == ROUND else "",
            "act_i": self.act_i,
            "round_len": self.round_len,
            "round_left": round(self.round_left, 1) if self.phase == ROUND else 0.0,
            "cleared": self.done_n,
            "posture_avg": round(self.posture_mean, 1),
            "posture_grade": self.posture_grade,
        }

    # ---------- persistence ----------

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.score = int(data.get("score", 0))
        self.streak = int(data.get("streak", 0))
        self.best_combo = int(data.get("best_combo", 0))
        self.rot = int(data.get("rot", 0))
        if data.get("date") != date.today().isoformat():
            return
        self.sit_s = float(data.get("sit_s", 0.0))
        self.sit_day = float(data.get("sit_day", 0.0))
        self.rounds = int(data.get("rounds", 0))
        self.hp_pool = float(
            data.get("hp_pool", max(0.0, 100.0 * (1.0 - self.sit_s / max(self.interval, 1.0))))
        )
        self._clamp_hp()
        if self.sit_s >= self.interval or self.hp_pool <= 0.5:
            self.phase = ALERT
            self.hp_pool = 0.0

    def save(self) -> None:
        payload = {
            "date": date.today().isoformat(),
            "score": self.score,
            "streak": self.streak,
            "best_combo": self.best_combo,
            "rot": self.rot,
            "sit_s": round(self.sit_s, 1),
            "sit_day": round(self.sit_day, 1),
            "rounds": self.rounds,
            "hp_pool": round(self.hp_pool, 1),
        }
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            return

    # ---------- helpers ----------

    def _toast(self, text: str, hold: float = 2.4) -> None:
        self.toast = text
        self.toast_t = hold

    def _pick_round(self) -> list:
        n = min(max(2, self.round_len), len(ACTS))
        order = [ACTS[(self.rot + i) % len(ACTS)] for i in range(len(ACTS))]
        picked = order[:n]
        self.rot = (self.rot + n) % len(ACTS)
        random.shuffle(picked)
        return picked

    def _start_round(self, early: bool = False) -> None:
        self.phase = ROUND
        self.sub = READY
        self.acts = self._pick_round()
        self.act_i = 0
        self.t_state = 0.0
        self.hold = 0.0
        self.peak = 0.0
        self.results = []
        self.round_score = 0
        self.round_time = 0.0
        self.combo = 0
        self.trans = 0.55
        self.early_hold = 0.0
        self.events.append("round_start")
        self.events.append("act_begin")
        self._toast("提前回血  这一组算你主动" if early else "回血开始  跟着屏幕做", 2.6)

    def _next_act(self) -> None:
        self.act_i += 1
        self.hold = 0.0
        self.peak = 0.0
        self.t_state = 0.0
        self.trans = 0.55
        if self.act_i >= len(self.acts) or self.round_left <= 0:
            self._end_round()
        else:
            self.sub = READY
            self.events.append("act_begin")

    def _clear_act(self) -> None:
        act = self.act
        secs = self.t_state
        g = grade_for(secs)
        pts = int(100 * GRADE_MUL[g]) + self.combo * 20
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.score += pts
        self.round_score += pts
        self.results.append(ActResult(act, True, secs, g, pts))
        self.sub = CLEAR
        self.t_state = 0.0
        self.events.append("act_clear")

    def _miss_act(self) -> None:
        self.combo = 0
        self.results.append(ActResult(self.act, False, self.t_state, "-", 0))
        self.sub = CLEAR
        self.t_state = 0.0
        self.events.append("act_miss")

    def _end_round(self) -> None:
        while len(self.results) < len(self.acts):
            idx = len(self.results)
            self.results.append(ActResult(self.acts[idx], False, 0.0, "-", 0))
        cleared = self.done_n
        full = cleared >= len(self.acts)
        bonus = 200 + self.streak * 40 if full else 60 * cleared
        self.score += bonus
        self.round_score += bonus
        self.rounds += 1
        self.streak = self.streak + 1 if full else 0
        self.round_posture = self.posture_mean
        self.sit_s = 0.0
        self.hp_pool = 100.0
        self.phase = SUMMARY
        self.t_state = 0.0
        self.posture_n = 0
        self.posture_sum = 0.0
        self.events.append("round_end")
        self.save()

    # ---------- main ----------

    def step(
        self,
        motion: Motion,
        dt: float,
        seen: bool,
        posture: float | None = None,
        chal_frac: float = 0.0,
        posture_bad: bool = False,
    ) -> None:
        dt = min(max(dt, 0.0), 2.0)
        self.toast_t = max(0.0, self.toast_t - dt)
        self.trans = max(0.0, self.trans - dt)
        self.energy_ema = 0.88 * self.energy_ema + 0.12 * float(motion.energy)
        moving = self.energy_ema > MOVE_ENERGY or motion.wings > 0.45 or motion.hands_up > 0.5

        # pose flickers while typing, so both directions decay instead of resetting
        if seen:
            self.seen_s = min(PRESENT_ON * 3, self.seen_s + dt)
            self.miss_s = max(0.0, self.miss_s - dt * 3.0)
            if self.seen_s >= PRESENT_ON:
                self.present = True
        else:
            self.miss_s += dt
            self.seen_s = max(0.0, self.seen_s - dt * 0.35)
            if self.miss_s >= PRESENT_OFF:
                self.present = False

        if posture is not None and seen:
            self.posture_n += 1
            self.posture_sum += float(posture)
            self.posture_avg = self.posture_mean
            if not posture_bad and float(posture) < POSTURE_BAD_SCORE:
                posture_bad = True

        if not self.present:
            self._step_away(dt)
            return

        self.away_s = 0.0
        if self.phase == AWAY:
            self.phase = ALERT if (self.sit_s >= self.interval or self.hp_pool <= 0.5) else MONITOR

        if self.phase == MONITOR:
            self._step_monitor(motion, dt, moving, posture_bad)
        elif self.phase == ALERT:
            self._step_alert(dt, moving, posture_bad)
        elif self.phase == ROUND:
            self._step_round(motion, dt, chal_frac)
        elif self.phase == SUMMARY:
            self.t_state += dt
            if self.t_state > SUMMARY_T or (self.t_state > 3.0 and motion.hands_up > 0.7):
                self.phase = MONITOR
                self.t_state = 0.0
                self.trans = 0.55
                self._toast("久坐已清零  接着干活", 2.4)

        self.save_cd += dt
        if self.save_cd > 15:
            self.save_cd = 0.0
            self.save()

    def _step_away(self, dt: float) -> None:
        if self.phase != AWAY:
            self.phase = AWAY
            self.t_state = 0.0
        self.away_s += dt
        if self.away_s > WALK_SEC:
            before = self.sit_s
            self.sit_s = max(0.0, self.sit_s - dt * 2.0)
            self.hp_pool = min(100.0, self.hp_pool + (before - self.sit_s) * self._sit_drain_rate())
            self._clamp_hp()
        if self.away_s > RESET_AWAY and self.sit_s > 1:
            self.sit_s = 0.0
            self.hp_pool = 100.0
            self.streak = 0
            self._toast("离开超过5分钟  久坐清零", 2.6)
            self.save()
        self.save_cd += dt
        if self.save_cd > 20:
            self.save_cd = 0.0
            self.save()

    def _step_monitor(self, motion: Motion, dt: float, moving: bool, posture_bad: bool = False) -> None:
        rate = self._sit_drain_rate()
        if moving:
            before = self.sit_s
            self.sit_s = max(0.0, self.sit_s - dt * 2.5)
            self.hp_pool = min(100.0, self.hp_pool + (before - self.sit_s) * rate)
            if motion.hands_up > 0.62 or motion.wings > 0.62:
                self.early_hold += dt
            else:
                self.early_hold = 0.0
            if self.early_hold >= VOLUNTARY_HOLD:
                self._start_round(early=True)
                return
        else:
            self.sit_s += dt
            self.sit_day += dt
            self.hp_pool -= rate * dt
            self.early_hold = 0.0
        # sitting bad posture keeps draining even if you fidget a bit
        if posture_bad:
            self.hp_pool -= POSTURE_DRAIN_PER_S * dt
            self.nag_t += dt
            if self.nag_t >= 40.0:
                self.nag_t = 0.0
                self._toast("坐姿不对  正在扣血", 2.2)
        else:
            self.nag_t = max(0.0, self.nag_t - dt)
        self._clamp_hp()
        if self.sit_s >= self.interval or self.hp_pool <= 0.5:
            self.hp_pool = 0.0
            self.phase = ALERT
            self.t_state = 0.0
            self.nag_t = 0.0
            why = "坐姿扣光了" if self.sit_s < self.interval else f"已经坐了{mmss(self.interval)}"
            self._toast(f"{why}  该回血了", 3.4)

    def _step_alert(self, dt: float, moving: bool, posture_bad: bool = False) -> None:
        self.sit_s += dt
        self.sit_day += dt
        self.hp_pool = 0.0
        self.t_state += dt
        self.nag_t += dt
        if self.nag_t >= NAG_EVERY:
            self.nag_t = 0.0
            self._toast(f"还在坐  已超时{mmss(self.overtime)}", 3.0)
        if moving:
            self._start_round()

    def _step_round(self, motion: Motion, dt: float, chal_frac: float) -> None:
        self.round_time += dt
        self.t_state += dt
        if self.sub == READY:
            if self.t_state >= READY_T:
                self.sub = PLAY
                self.t_state = 0.0
            return
        if self.sub == CLEAR:
            if self.t_state >= CLEAR_T:
                self._next_act()
            return
        # the scene owns the challenge; we only react to it being finished
        if chal_frac >= 1.0:
            self._clear_act()
        elif self.round_left <= 0:
            self._miss_act()
            self.sub = CLEAR
            self.t_state = CLEAR_T

    def pop_events(self) -> list:
        out = self.events
        self.events = []
        return out
