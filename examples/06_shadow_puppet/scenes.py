#!/usr/bin/env python3
"""Top-half pixel stage: one themed challenge screen per action."""

from __future__ import annotations

import random

from gestures import Motion
from loop import ACT_BY_ID
from pixel_ui import (
    AZURE,
    BIRD,
    BIRD_PAL,
    CLOUD,
    CLOUD_PAL,
    CYAN,
    EAGLE_DN,
    EAGLE_MID,
    EAGLE_PAL,
    EAGLE_UP,
    GRAY,
    GREEN,
    LIME,
    MUG,
    MUG_PAL,
    NAVY,
    NIGHT,
    NOTE,
    NOTE_PAL,
    ORANGE,
    PLANT,
    PLANT_PAL,
    PLUM,
    RED,
    SILVER,
    SLATE,
    STAR,
    STAR_PAL,
    TEAL,
    WHITE,
    YELLOW,
    PixelScreen,
)

STAGE_H = 120
GROUND = 106
AV_X = 160
# Steve body below shoulders = 36; shoes land on GROUND
AV_SH_Y = GROUND - 36

# downhill ski run: items fall toward the skier, who slides left/right
SKI_LANES = (100, 130, 160, 190, 220)
SKI_SWING = 48.0
SKI_HIT_Y = 88
SKI_SPEED = 44.0

# chrome-dino style runner
CACTUS_H = 28
CACTUS_W = 18
DINO_SPEED = 78.0
JUMP_V = -240.0   # higher leap so you clearly clear the cactus
JUMP_G = 520.0
DINO_HIT_HALF = 16  # steve + cactus overlap half-width

# eagle flight — alt 0 on ground, ~56 at the flag
EAGLE_MAX_ALT = 56.0
EAGLE_GRAVITY = 95.0
EAGLE_FLAP_BOOST = 70.0
EAGLE_GLIDE = 110.0
EAGLE_FLAP_LIFT = 160.0  # continuous climb while arms keep moving

ACCENT = {
    "wings": YELLOW,
    "eagle": ORANGE,
    "wave": CYAN,
    "ski": AZURE,
    "piano": PLUM,
    "dino": LIME,
    "turn": GREEN,
    "nod": SILVER,
}


def accent_of(scene: str):
    return ACCENT.get(scene, YELLOW)


class Stage:
    """Scene simulation + challenge progress. One instance for the whole run."""

    def __init__(self) -> None:
        self.scene = ""
        self.act = ACT_BY_ID["wings"]
        self.t = 0.0
        self.scroll = 0.0
        self.got = 0.0
        self.need = 1.0
        self.kind = "reps"
        self.text = ""
        self.hint = ""
        self.pop = 0.0
        self.fail = 0.0
        self.avatar_dx = 0.0
        self.avatar_dy = 0.0
        # per-scene
        self.armed = True
        self.sign = 0.0
        self.alt = 0.0
        self.vy = 0.0
        self.gates: list[dict] = []
        self.gate_msg = ""
        self.msg_t = 0.0
        self.obs = 300.0
        self.obs_cleared = False
        self.air_over = 0.0  # max shoe height while overlapping a cactus

        self.keys_lit: dict[int, float] = {}
        self.notes: list[list[float]] = []
        self.press_base: dict[int, float] = {}
        self.press_armed: dict[int, bool] = {}
        self.tips: list[tuple] = []
        self.left_got = 0.0
        self.right_got = 0.0
        self.nod_base = -1
        self.target_key = 3
        self.jump_flash = 0.0
        self.hands_up = 0.0
        self.jump_ready = True
        self.wing_beat = 0.0
        self.falling = False
        self.left_fill = 0.0
        self.right_fill = 0.0
        self.gust_t = 0.0

    # ---------- lifecycle ----------

    def begin(self, act: dict) -> None:
        self.act = act
        self.scene = act["scene"]
        self.kind = act.get("kind", "reps")
        self.need = float(act.get("need", 1))
        self.got = 0.0
        self.t = 0.0
        self.pop = 0.0
        self.fail = 0.0
        self.armed = True
        self.sign = 0.0
        self.alt = 0.0
        self.vy = 0.0
        self.avatar_dx = 0.0
        self.avatar_dy = 0.0
        self.obs = 300.0
        self.obs_cleared = False
        self.air_over = 0.0
        self.keys_lit = {}
        self.notes = []
        self.press_base = {}
        self.press_armed = {}
        self.tips = []
        self.left_got = 0.0
        self.right_got = 0.0
        self.nod_base = -1
        self.target_key = 3
        self.gate_msg = ""
        self.msg_t = 0.0
        self.jump_flash = 0.0
        self.hands_up = 0.0
        self.jump_ready = True
        self.wing_beat = 0.0
        self.falling = False
        self.left_fill = 0.0
        self.right_fill = 0.0
        self.gust_t = 0.0
        self.gates = [self._ski_item(18.0 - i * 34.0) for i in range(4)]
        self._sync_text()

    def _ski_item(self, y: float) -> dict:
        kind = "flag" if random.random() < 0.62 else "tree"
        return {"x": float(random.choice(SKI_LANES)), "y": y, "kind": kind, "state": 0}

    @property
    def frac(self) -> float:
        return min(1.0, self.got / max(self.need, 0.01))

    @property
    def done(self) -> bool:
        return self.got >= self.need

    def _sync_text(self) -> None:
        if self.kind == "hold":
            if self.scene == "wings":
                ok = self.left_fill >= 0.85 and self.right_fill >= 0.85
                wind = " 有风！" if self.gust_t > 0 else ""
                self.text = f"{min(self.got, self.need):.1f}/{self.need:.0f}秒" + (
                    " 撑住！" + wind if ok else " 左右撑满" + wind
                )
            else:
                self.text = f"{min(self.got, self.need):.1f} / {self.need:.0f} 秒"
        elif self.scene == "turn":
            self.text = f"左 {int(self.left_got)} / 右 {int(self.right_got)}  共 {int(self.need)}"
        elif self.scene == "piano":
            self.text = f"{int(self.got)}/{int(self.need)}  按黄键"
        elif self.scene == "eagle":
            if self.falling:
                cue = "失重下坠！快挥翅"
            elif self.alt < 4:
                cue = "展开双臂上下挥"
            elif self.done:
                cue = "抓到旗子！"
            else:
                cue = f"高度 {int(self.alt):02d}"
            self.text = f"{int(self.got)}/{int(self.need)}  {cue}"
        elif self.scene == "dino":
            if self.avatar_dy < -1:
                cue = "跳起来了"
            elif AV_X < self.obs < AV_X + 100:
                cue = "仙人掌来了快跳！"
            elif self.hands_up >= 0.20:
                cue = "放下再举"
            elif self.hands_up > 0.08:
                cue = "再举一点"
            else:
                cue = "双手举到肩上→跳"
            self.text = f"{int(self.got)}/{int(self.need)}  {cue}"
        else:
            self.text = f"{int(self.got)} / {int(self.need)}"

    def _tick(self, n: float = 1.0) -> None:
        self.got = min(self.need, self.got + n)
        self.pop = 0.45

    # ---------- simulation ----------

    def step(self, motion: Motion, hands, dt: float, live: bool) -> None:
        self.t += dt
        self.scroll += dt * 26.0
        self.pop = max(0.0, self.pop - dt)
        self.fail = max(0.0, self.fail - dt)
        self.msg_t = max(0.0, self.msg_t - dt)
        self.jump_flash = max(0.0, self.jump_flash - dt)
        if self.msg_t <= 0:
            self.gate_msg = ""
        if live:
            fn = getattr(self, f"_sim_{self.scene}", None)
            if fn is not None:
                fn(motion, hands, dt)
        self._sync_text()

    def _edge(self, value: float, on: float, off: float) -> bool:
        """One count per crossing, needs to fall back below `off` to re-arm."""
        if self.armed and value >= on:
            self.armed = False
            return True
        if value <= off:
            self.armed = True
        return False

    def _sim_wings(self, motion: Motion, hands, dt: float) -> None:
        """Both arms must T-pose; hold through wind gusts."""
        # smooth side meters
        self.left_fill += (float(motion.wing_l) - self.left_fill) * min(1.0, dt * 6.0)
        self.right_fill += (float(motion.wing_r) - self.right_fill) * min(1.0, dt * 6.0)
        # gust every ~3.2s for 1.1s
        phase = self.t % 3.2
        self.gust_t = 1.1 - phase if phase < 1.1 else 0.0
        both = self.left_fill >= 0.82 and self.right_fill >= 0.82
        strong = motion.wing_l >= 0.70 and motion.wing_r >= 0.70
        if self.gust_t > 0 and not strong:
            self.got = max(0.0, self.got - dt * 1.4)
            self.fail = 0.4
            if self.msg_t <= 0:
                self.gate_msg = "被风吹散！"
                self.msg_t = 0.5
        elif both:
            self.got = min(self.need, self.got + dt)
            self.pop = 0.2
            if self.gust_t > 0 and self.msg_t <= 0:
                self.gate_msg = "顶住风！"
                self.msg_t = 0.35
        else:
            self.got = max(0.0, self.got - dt * 0.55)

    def _sim_eagle(self, motion: Motion, hands, dt: float) -> None:
        """Fly: T-pose wings out + keep flapping. Unlike jump — no chair-bounce."""
        dt = min(float(dt), 0.08)
        self.wing_beat = float(motion.flap)
        # must look like wings (horizontal reach), not "hands up" jump
        open_wings = motion.wings >= 0.32 or (motion.wing_l + motion.wing_r) * 0.5 >= 0.38
        flapping = motion.flap >= 0.22 and (open_wings or motion.wings >= 0.22)

        # count a flap beat (low threshold for ~6 FPS)
        flapped = self._edge(motion.flap, 0.28, 0.08)
        if flapped:
            self._tick()
            self.vy += EAGLE_FLAP_BOOST
            self.gate_msg = "起飞！"
            self.msg_t = 0.3
            self.jump_flash = 0.25
            self.fail = 0.0

        # continuous lift — don't require a perfect edge every time
        if flapping:
            self.vy += EAGLE_FLAP_LIFT * dt * (0.5 + 0.5 * motion.flap)
        if open_wings:
            self.vy += EAGLE_GLIDE * dt
            grav = EAGLE_GRAVITY * (0.25 if flapping else 0.45)
        else:
            grav = EAGLE_GRAVITY * 1.35
        self.vy -= grav * dt
        self.vy = float(max(-90.0, min(150.0, self.vy)))

        self.alt = float(max(0.0, min(EAGLE_MAX_ALT, self.alt + self.vy * dt)))
        if self.alt <= 0.0:
            self.alt = 0.0
            if self.vy < 0.0:
                self.vy = 0.0

        self.avatar_dy = -self.alt
        climb = max(0.0, self.vy)
        self.scroll += (18.0 + self.alt * 1.4 + climb * 0.55) * dt

        # only scream "falling" when arms are really down
        self.falling = (not open_wings) and self.vy < -12.0 and self.alt > 8.0
        if self.falling:
            self.fail = max(self.fail, 0.35)
            if self.msg_t <= 0:
                self.gate_msg = "失重下坠！"
                self.msg_t = 0.4
        elif open_wings and flapping and self.msg_t <= 0 and self.alt > 2:
            self.gate_msg = "飞起来了"
            self.msg_t = 0.25
            self.fail = 0.0

        if self.got >= self.need and self.alt >= EAGLE_MAX_ALT - 8:
            self.gate_msg = "抓到旗子！"
            self.msg_t = 1.0
            self.fail = 0.0
            self.falling = False
            self.alt = EAGLE_MAX_ALT
            self.vy = 0.0

    def _sim_wave(self, motion: Motion, hands, dt: float) -> None:
        if motion.wave < 0.25:
            return
        s = 1.0 if motion.wave_side > 0.35 else (-1.0 if motion.wave_side < -0.35 else 0.0)
        if s != 0.0 and s != self.sign:
            self.sign = s
            self._tick()

    def _sim_ski(self, motion: Motion, hands, dt: float) -> None:
        self.avatar_dx = motion.lean_dir * SKI_SWING
        me = AV_X + self.avatar_dx
        for g in self.gates:
            g["y"] += SKI_SPEED * dt
            if g["state"] == 0 and abs(g["y"] - SKI_HIT_Y) < 8 and abs(g["x"] - me) < 18:
                g["state"] = 1
                self.msg_t = 1.1
                if g["kind"] == "flag":
                    self._tick()
                    self.gate_msg = "碰到旗子"
                else:
                    self.got = max(0.0, self.got - 1.0)
                    self.fail = 0.6
                    self.gate_msg = "撞树了"
            if g["y"] > STAGE_H + 12:
                top = min(gg["y"] for gg in self.gates)
                g.update(self._ski_item(min(14.0, top - 36.0)))

    def _sim_dino(self, motion: Motion, hands, dt: float) -> None:
        """Runner: cactus comes from the right; only counts if shoes clear its tip."""
        dt = min(float(dt), 0.05)  # keep jump arc stable at low FPS
        self.hands_up = float(motion.hands_up)
        self.jump_ready = bool(motion.jump_armed)

        if motion.jump >= 0.5 and self.avatar_dy >= -2.0:
            self.vy = JUMP_V
            self.jump_flash = 0.45
            self.gate_msg = "跳！"
            self.msg_t = 0.35

        self.vy += JUMP_G * dt
        self.avatar_dy = min(0.0, self.avatar_dy + self.vy * dt)
        if self.avatar_dy >= 0.0:
            self.avatar_dy = 0.0
            self.vy = 0.0

        shoe = -self.avatar_dy  # how high the feet are
        self.obs -= DINO_SPEED * dt

        # overlap band while cactus crosses Steve
        half = DINO_HIT_HALF + CACTUS_W // 2
        overlapping = abs(self.obs - AV_X) <= half
        if overlapping:
            self.air_over = max(self.air_over, shoe)
        elif self.obs < AV_X - half and not self.obs_cleared:
            # cactus just finished passing Steve — judge the leap
            self.obs_cleared = True
            if self.air_over >= CACTUS_H - 2:
                self._tick()
                self.gate_msg = "跳过！"
                self.msg_t = 0.8
                self.fail = 0.0
            else:
                self.fail = 0.65
                self.gate_msg = "撞到了"
                self.msg_t = 0.8
            self.air_over = 0.0

        if self.obs < -40:
            self.obs = 280.0 + random.random() * 60.0
            self.obs_cleared = False
            self.air_over = 0.0

    def _sim_turn(self, motion: Motion, hands, dt: float) -> None:
        d = motion.turn_dir
        if self.armed and abs(d) >= 0.6:
            self.armed = False
            if d < 0 and self.left_got < self.need:
                self.left_got += 1
            elif d > 0 and self.right_got < self.need:
                self.right_got += 1
            self.pop = 0.45
        elif abs(d) <= 0.22:
            self.armed = True
        self.got = min(self.left_got, self.right_got)

    def _sim_nod(self, motion: Motion, hands, dt: float) -> None:
        if self.nod_base < 0:
            self.nod_base = motion.nod_count
        n = max(0, motion.nod_count - self.nod_base)
        if n > self.got:
            self.pop = 0.55
            self.gate_msg = "点！"
            self.msg_t = 0.45
        self.got = min(self.need, n)
        # keep feet planted — bobble is drawn on the head only
        self.avatar_dy = 0.0

    def _sim_piano(self, motion: Motion, hands, dt: float) -> None:
        """Hit the highlighted key — random freestyle presses don't count."""
        for k in list(self.keys_lit):
            self.keys_lit[k] = max(0.0, self.keys_lit[k] - dt * 2.2)
        for n in self.notes:
            n[1] -= 40.0 * dt
        self.notes = [n for n in self.notes if n[1] > 16]
        self.tips = []
        n_keys = 10

        def hit(key: int, good: bool) -> None:
            self.keys_lit[key] = 1.0
            kw = max(1, (320 - 12) // n_keys)
            self.notes.append([float(8 + key * kw), float(GROUND - 26)])
            if good:
                self._tick()
                self.target_key = (self.target_key + 2 + int(self.t * 3) % 3) % n_keys
                self.gate_msg = "好听！"
                self.msg_t = 0.4
                self.fail = 0.0
            else:
                self.fail = 0.45
                self.gate_msg = "按黄键！"
                self.msg_t = 0.5

        used_hands = False
        if hands is not None and getattr(hands, "hands", None):
            for hi, hand in enumerate(hands.hands[:2]):
                tip = hand.xy[8]
                span = max(float(hand.span), 40.0)
                self.tips.append((float(tip[0]), float(tip[1]), hi))
                base = self.press_base.get(hi)
                if base is None:
                    self.press_base[hi] = float(tip[1])
                    self.press_armed[hi] = True
                    continue
                drop = (float(tip[1]) - base) / span
                if self.press_armed.get(hi, True) and drop > 0.32:
                    self.press_armed[hi] = False
                    key = self._key_at(float(tip[0]), n_keys)
                    hit(key, abs(key - self.target_key) <= 1)
                    used_hands = True
                elif drop < 0.12:
                    self.press_armed[hi] = True
                self.press_base[hi] = base * 0.9 + float(tip[1]) * 0.1

        # pose fallback when hand model is missing / flaky
        if not used_hands:
            key = int(round(motion.piano_x * (n_keys - 1)))
            key = max(0, min(n_keys - 1, key))
            if self._edge(motion.piano, 0.45, 0.18):
                hit(key, abs(key - self.target_key) <= 1)

    def _key_at(self, x_img: float, n_keys: int = 10) -> int:
        k = int(x_img / 1280.0 * n_keys)
        return max(0, min(n_keys - 1, k))

    # ---------- draw helpers ----------

    def _draw_cactus(self, scr: PixelScreen, x: int, ground: int, h: int = CACTUS_H) -> None:
        """Chunky cactus ~Steve-leg height so the runner reads as a game."""
        trunk = 10
        tx = x - trunk // 2
        scr.rect(tx - 1, ground - h - 1, trunk + 2, h + 2, NIGHT)
        scr.rect(tx, ground - h, trunk, h, GREEN)
        scr.rect(tx + 2, ground - h, 3, h, LIME)
        # left arm
        ay = ground - h + 6
        scr.rect(tx - 11, ay, 12, 7, NIGHT)
        scr.rect(tx - 10, ay + 1, 10, 5, GREEN)
        scr.rect(tx - 10, ay - 8, 6, 14, NIGHT)
        scr.rect(tx - 9, ay - 7, 4, 12, GREEN)
        # right arm
        by = ground - h + 14
        scr.rect(tx + trunk - 1, by, 12, 7, NIGHT)
        scr.rect(tx + trunk, by + 1, 10, 5, GREEN)
        scr.rect(tx + trunk + 5, by - 8, 6, 14, NIGHT)
        scr.rect(tx + trunk + 6, by - 7, 4, 12, GREEN)

    def _draw_tree(self, scr: PixelScreen, x: int, y: int, hit: bool = False) -> None:
        leaf = RED if hit else GREEN
        leaf2 = ORANGE if hit else TEAL
        trunk = NIGHT if not hit else RED
        scr.tri_up(x - 14, y - 28, 28, 18, leaf)
        scr.tri_up(x - 11, y - 20, 22, 14, leaf2)
        scr.tri_up(x - 8, y - 12, 16, 10, leaf)
        scr.rect(x - 2, y - 6, 4, 8, trunk)

    def _draw_flag(self, scr: PixelScreen, x: int, y: int, got: bool = False) -> None:
        col = LIME if got else YELLOW
        scr.rect(x, y - 26, 3, 28, NIGHT)
        scr.rect(x + 3, y - 26, 16, 12, col)
        scr.rect(x + 3, y - 26, 16, 2, NIGHT)
        scr.rect(x + 3, y - 16, 16, 2, NIGHT)

    def _draw_cloud(self, scr: PixelScreen, x: int, y: int, s: int = 2) -> None:
        """s=1 tiny, s=2 game-size cloud."""
        if s <= 1:
            scr.sprite(x, y, CLOUD, CLOUD_PAL)
            return
        scr.rect(x + 6, y, 22, 8, WHITE)
        scr.rect(x, y + 4, 34, 10, WHITE)
        scr.rect(x + 4, y + 2, 26, 4, SILVER)

    # ---------- background ----------

    def draw_bg(self, scr: PixelScreen) -> None:
        fn = getattr(self, f"_bg_{self.scene}", None)
        if fn is None:
            scr.rect(0, 0, scr.lw, STAGE_H, NAVY)
            return
        fn(scr)

    def _sky(self, scr: PixelScreen, top, bottom, ground_col=GREEN) -> None:
        scr.rect(0, 0, scr.lw, STAGE_H, top)
        scr.rect(0, GROUND - 28, scr.lw, 28 + (STAGE_H - GROUND), bottom)
        scr.rect(0, GROUND, scr.lw, 2, ground_col)
        scr.rect(0, GROUND + 2, scr.lw, STAGE_H - GROUND - 2, ground_col)

    def _bg_wings(self, scr: PixelScreen) -> None:
        self._sky(scr, NAVY, TEAL, GREEN)
        scr.disc(272, 26, 12, YELLOW)
        scr.disc(272, 26, 7, ORANGE)
        for x, w, h in ((8, 100, 48), (70, 80, 38), (170, 110, 44)):
            scr.tri_up(x, GROUND - h, w, h, SLATE)
        # wind streaks during gust
        if self.gust_t > 0:
            for i in range(6):
                y = 40 + i * 10
                x = int((self.t * 90 + i * 40) % (scr.lw + 20)) - 10
                scr.rect(x, y, 18, 2, SILVER)
        hit = self.frac >= 1.0
        for left, fill in ((True, self.left_fill), (False, self.right_fill)):
            x = 4 if left else scr.lw - 30
            ready = fill >= 0.82
            col = LIME if hit else (YELLOW if ready else (ORANGE if fill > 0.4 else SLATE))
            scr.window(x, 28, 26, 56, col, NIGHT, 255)
            scr.text(x + 4, 30, "左" if left else "右", WHITE, 10)
            bars = int(round(min(1.0, fill) * 5))
            for i in range(5):
                scr.rect(x + 6, 74 - i * 8, 14, 6, col if i < bars else SLATE)
        # center hold meter
        scr.window(110, 100, 100, 14, LIME if hit else YELLOW, NIGHT, 255)
        scr.seg_bar(114, 104, 92, 6, self.frac, LIME if hit else YELLOW, seg=5)

    def _bg_eagle(self, scr: PixelScreen) -> None:
        """Looking sideways: world scrolls down as Steve climbs toward the flag."""
        # sky bands — deeper blue higher up
        scr.rect(0, 0, scr.lw, STAGE_H, AZURE)
        scr.rect(0, 0, scr.lw, 28, NAVY)
        # sun
        scr.disc(40, 22, 9, YELLOW)
        # vertical parallax: clouds & cliffs rush downward with scroll
        drift = self.scroll * 1.8
        for i in range(6):
            y = int((i * 28 + drift) % (STAGE_H - 8)) - 12
            if y >= STAGE_H - 4:
                continue
            x = 20 + (i * 53) % 260
            self._draw_cloud(scr, x, y, 2)
        # distant cliffs sliding down — keep inside the stage band
        for i in range(5):
            y = int((i * 36 + drift * 0.7) % (STAGE_H - 10)) - 4
            if y + 28 > STAGE_H:
                continue
            x = 8 if i % 2 == 0 else scr.lw - 50
            scr.tri_up(x, y, 42, 28, SLATE)
            scr.tri_up(x + 8, y + 10, 28, 18, NIGHT)
        # ground only when near takeoff
        if self.alt < 18:
            gy = min(GROUND + int(self.alt * 1.2), STAGE_H - 2)
            scr.rect(0, gy, scr.lw, STAGE_H - gy, TEAL)
            scr.rect(0, gy, scr.lw, 2, LIME)
            for i in range(0, scr.lw, 16):
                scr.rect(i, min(gy + 4, STAGE_H - 1), 8, 2, GREEN)
        # flag fixed near the top — climb to it
        fx = scr.lw - 48
        fy = 26
        pole_h = 36
        scr.rect(fx + 8, fy, 3, pole_h, SLATE)
        col = LIME if self.done else RED
        scr.rect(fx + 11, fy, 22, 12, col)
        scr.rect(fx + 11, fy, 22, 2, NIGHT)
        if self.done:
            scr.sprite(fx + 14, fy + 14, STAR, STAR_PAL)
        # altitude tape on the left
        scr.rect(4, 24, 6, 70, NIGHT)
        scr.rect(5, 25, 4, 68, SLATE)
        mark = 25 + 68 - int((self.alt / EAGLE_MAX_ALT) * 68)
        scr.rect(3, mark - 2, 8, 4, LIME if not self.falling else RED)

    def draw_wings(self, scr: PixelScreen, ax: int, ay: int) -> None:
        """Big eagle wings behind Steve; flap opens/closes them."""
        if self.scene != "eagle":
            return
        beat = max(0.0, min(1.0, self.wing_beat))
        # pick sprite frame
        if beat > 0.7:
            spr = EAGLE_UP
        elif beat > 0.35:
            spr = EAGLE_MID
        else:
            spr = EAGLE_DN
        # chunky wings (scaled sprites + fill)
        spread = 10 + int(beat * 16)
        for side, flip in ((-1, True), (1, False)):
            ox = ax + side * (8 + spread // 2)
            oy = ay + 2
            # membrane
            for i in range(spread):
                t = i / max(1, spread - 1)
                yoff = int((1.0 - beat) * 6 * t) if self.falling else int(-beat * 4 * t)
                w = 5 - int(t * 2)
                scr.rect(ox + side * i - w // 2, oy + yoff, w, 4, ORANGE)
                scr.rect(ox + side * i - w // 2, oy + yoff + 1, w, 2, YELLOW)
            # tip feather
            tip_x = ox + side * spread
            scr.rect(tip_x - 1, oy - 2 - int(beat * 3), 4, 8, NIGHT)
            scr.rect(tip_x, oy - 1 - int(beat * 3), 2, 6, ORANGE)
            scr.sprite(ax + side * 18 - 4, ay - 2, spr, EAGLE_PAL)

    def _bg_wave(self, scr: PixelScreen) -> None:
        self._sky(scr, PLUM, SLATE, GRAY)
        off = int(self.scroll * 1.6) % 120
        for c in range(4):
            x = 8 + c * 100 - off
            h = 40 + (c % 3) * 6
            scr.rect(x, GROUND - h, 88, h, SLATE)
            scr.frame(x, GROUND - h, 88, h, NIGHT)
            for wd in range(4):
                for row in range(2):
                    lit = (c + wd + row + int(self.got)) % 2 == 0
                    scr.rect(x + 8 + wd * 18, GROUND - h + 8 + row * 14, 12, 10, CYAN if lit else AZURE)
            scr.rect(x + 12, GROUND - 4, 12, 4, NIGHT)
            scr.rect(x + 60, GROUND - 4, 12, 4, NIGHT)

    def _bg_ski(self, scr: PixelScreen) -> None:
        """Downhill run: slope scrolls toward the skier."""
        scr.rect(0, 0, scr.lw, STAGE_H, WHITE)
        scr.rect(0, 0, scr.lw, 22, AZURE)
        scr.rect(0, 22, scr.lw, 3, SILVER)
        self._draw_cloud(scr, 40, 6, 2)
        self._draw_cloud(scr, 200, 8, 2)
        drift = self.scroll * 1.6
        # perspective lane dashes
        for i in range(10):
            y = int((i * 14 + drift) % (STAGE_H - 26)) + 26
            w = 6 + (y - 26) // 8
            scr.rect(AV_X - w // 2, y, w, 2, SILVER)
            scr.rect(90, y, 10 + (y // 20), 2, SILVER)
            scr.rect(220, y, 10 + (y // 20), 2, SILVER)
        for i in range(8):
            y = int((i * 18 + drift * 1.2) % (STAGE_H - 22)) + 22
            for x in (4, scr.lw - 18):
                scr.rect(x + 4, y, 4, 10, RED)
                scr.rect(x, y + 10, 12, 3, NIGHT)
        scr.rect(0, SKI_HIT_Y + 8, scr.lw, 1, SILVER)
        for g in self.gates:
            gx, gy = int(g["x"]), int(g["y"])
            if gy < 18 or gy > STAGE_H + 4:
                continue
            if g["kind"] == "flag":
                self._draw_flag(scr, gx, gy, g["state"] == 1)
            else:
                self._draw_tree(scr, gx, gy, g["state"] == 1)

    def _bg_dino(self, scr: PixelScreen) -> None:
        # day desert runner
        scr.rect(0, 0, scr.lw, STAGE_H, AZURE)
        scr.rect(0, 0, scr.lw, 18, (200, 160, 80))  # warm sky top BGR-ish
        scr.rect(0, GROUND - 36, scr.lw, 36, (90, 170, 210))
        # distant hills
        for x, w, h in ((0, 70, 22), (50, 90, 28), (140, 80, 20), (220, 100, 26)):
            scr.tri_up(x, GROUND - 36 - h // 2, w, h, SLATE)
        scr.disc(40, 28, 10, YELLOW)
        # parallax ground detail
        scr.rect(0, GROUND - 2, scr.lw, 2, NIGHT)
        scr.rect(0, GROUND, scr.lw, STAGE_H - GROUND, (40, 120, 60))
        for i in range(0, scr.lw + 20, 18):
            x = (i + int(self.scroll * 3.2)) % (scr.lw + 20) - 10
            scr.rect(x, GROUND + 3, 10, 2, LIME)
            scr.rect(x + 4, GROUND + 7, 6, 1, GREEN)
        # shadow under Steve — shrinks when airborne so the leap reads
        sh = max(2, 14 + int(self.avatar_dy // 2))
        scr.rect(AV_X - sh, GROUND - 1, sh * 2, 3, NIGHT)
        # danger line: cactus coming from the right
        ox = int(self.obs)
        if ox > AV_X + 20:
            scr.rect(ox - 2, GROUND - CACTUS_H - 4, 4, 4, RED)
        if -40 < ox < scr.lw + 20:
            self._draw_cactus(scr, ox, GROUND, CACTUS_H)
            # if overlapping and not high enough, flash cactus tip
            if abs(ox - AV_X) <= DINO_HIT_HALF + CACTUS_W // 2 and -self.avatar_dy < CACTUS_H - 2:
                scr.rect(ox - 6, GROUND - CACTUS_H - 2, 12, 3, RED)

    def _bg_turn(self, scr: PixelScreen) -> None:
        self._sky(scr, TEAL, SLATE, GREEN)
        self._draw_cloud(scr, 80, 16, 2)
        self._draw_cloud(scr, 190, 20, 2)
        for left in (True, False):
            x = 4 if left else scr.lw - 52
            got = self.left_got if left else self.right_got
            col = LIME if got >= self.need else (YELLOW if got else SLATE)
            scr.window(x, 28, 48, 58, col, NAVY, 255)
            scr.sprite(x + 18, 38, BIRD if left else PLANT, BIRD_PAL if left else PLANT_PAL)
            scr.pf(x + 10, 64, f"{int(got):02d}/{int(self.need):02d}", WHITE, 1)
            if left:
                scr.text(x + 8, 78, "左转", WHITE if got else SILVER, 10)
            else:
                scr.text(x + 8, 78, "右转", WHITE if got else SILVER, 10)

    def _bg_nod(self, scr: PixelScreen) -> None:
        # office desk — props sized for bobblehead Steve
        self._sky(scr, (90, 55, 40), SLATE, GRAY)
        scr.rect(0, 0, scr.lw, 22, NIGHT)
        # window
        scr.rect(18, 28, 52, 36, AZURE)
        scr.frame(18, 28, 52, 36, SILVER)
        scr.rect(42, 28, 2, 36, SILVER)
        scr.rect(18, 44, 52, 2, SILVER)
        # desk
        scr.rect(12, GROUND - 22, 110, 6, SILVER)
        scr.rect(12, GROUND - 16, 110, 16, GRAY)
        scr.rect(16, GROUND - 16, 4, 16, NIGHT)
        scr.rect(114, GROUND - 16, 4, 16, NIGHT)
        # monitor
        scr.rect(36, GROUND - 48, 44, 28, NIGHT)
        scr.rect(38, GROUND - 46, 40, 22, TEAL)
        scr.rect(54, GROUND - 20, 8, 4, NIGHT)
        # mug
        scr.rect(90, GROUND - 34, 14, 12, SILVER)
        scr.rect(92, GROUND - 32, 10, 8, WHITE)
        scr.rect(104, GROUND - 30, 4, 7, SILVER)
        todo = ("日报", "周会", "对齐", "复盘", "收工", "下班")
        n = int(self.need)
        for i in range(n):
            x = scr.lw - 72
            y = 24 + i * 13
            done = i < self.got
            scr.window(x, y, 66, 12, LIME if done else SLATE, NAVY, 255)
            scr.rect(x + 3, y + 3, 6, 6, LIME if done else NIGHT)
            if done:
                scr.rect(x + 4, y + 5, 4, 2, WHITE)
            if i < len(todo):
                scr.text(x + 14, y + 1, todo[i], WHITE if done else SILVER, 10)
        for i in range(int(self.got)):
            scr.sprite(140 + (i % 3) * 12, 28 + (i // 3) * 12, STAR, STAR_PAL)

    def _bg_piano(self, scr: PixelScreen) -> None:
        scr.rect(0, 0, scr.lw, STAGE_H, NIGHT)
        scr.rect(0, 0, scr.lw, GROUND - 28, PLUM)
        for i in range(5):
            self._draw_cloud(scr, 20 + i * 60, 10 + (i % 2) * 6, 1)
        for n in self.notes:
            scr.sprite(int(n[0]), int(n[1]), NOTE, NOTE_PAL)
        keys = 10
        kw = (scr.lw - 12) // keys
        scr.rect(2, GROUND - 30, scr.lw - 4, 34, NIGHT)
        scr.rect(4, GROUND - 28, scr.lw - 8, 30, SLATE)
        for i in range(keys):
            x = 6 + i * kw
            lit = self.keys_lit.get(i, 0.0)
            target = i == self.target_key
            if lit > 0.3:
                col = LIME
            elif target:
                col = YELLOW
            else:
                col = WHITE
            scr.rect(x, GROUND - 24, kw - 1, 26, col)
            scr.frame(x, GROUND - 24, kw - 1, 26, NIGHT)
            if i % 7 not in (2, 6):
                scr.rect(x + max(1, kw - 5), GROUND - 24, 4, 15, NIGHT)
            if target:
                # big arrow above the key to press
                scr.tri_up(x + kw // 2 - 5, GROUND - 38, 10, 10, YELLOW)
                scr.rect(x + kw // 2 - 2, GROUND - 30, 4, 6, YELLOW)
        scr.text(8, 86, "只按黄色键", YELLOW, 12)

    # ---------- foreground ----------

    def draw_fg(self, scr: PixelScreen) -> None:
        if self.scene == "ski":
            fx = int(AV_X + self.avatar_dx)
            foot = GROUND + int(self.avatar_dy)
            for dx in (-12, 2):
                scr.rect(fx + dx - 1, foot + 1, 14, 4, NIGHT)
                scr.rect(fx + dx, foot + 2, 12, 2, CYAN)
                scr.rect(fx + dx + 10, foot + 2, 2, 2, AZURE)
        if self.scene == "dino":
            # coach: bounce in chair (not arm-flap like eagle)
            hx, hy, hw, hh = 6, 40, 52, 58
            ready = self.jump_ready and self.avatar_dy >= -1
            scr.window(hx, hy, hw, hh, LIME if not ready else YELLOW, NIGHT, 255)
            scr.text(hx + 4, hy + 3, "椅上颠", YELLOW, 11)
            cx, cy = hx + 26, hy + 42
            bounce = 0 if self.avatar_dy >= -1 else 6
            scr.rect(cx - 3, cy - 14 - bounce, 6, 10, SILVER)
            scr.rect(cx - 4, cy - 20 - bounce, 8, 7, SILVER)
            scr.rect(cx - 10, cy - 10 - bounce, 6, 3, SLATE)
            scr.rect(cx + 4, cy - 10 - bounce, 6, 3, SLATE)
            scr.rect(hx + 6, hy + 48, 40, 6, SLATE)
            fill = 38 if self.avatar_dy < -1 else (8 if not self.jump_ready else 20)
            scr.rect(hx + 7, hy + 49, fill, 4, LIME if self.avatar_dy < -1 else YELLOW)
            if self.avatar_dy < -1:
                tip = "跳！"
            elif not self.jump_ready:
                tip = "落下"
            else:
                tip = "颠身"
            scr.pf(hx + 14, hy + 22, tip, WHITE, 1)
            if self.jump_flash > 0:
                scr.text(AV_X - 10, GROUND - 52 + int(self.avatar_dy), "跳", LIME, 16)
        if self.scene == "eagle":
            ay = AV_SH_Y + int(self.avatar_dy)
            if self.falling:
                scr.text(AV_X - 34, ay - 28, "下坠！", RED, 14)
            elif self.jump_flash > 0:
                scr.text(AV_X - 18, ay - 28, "起飞", LIME, 14)
            if self.done:
                scr.text(AV_X - 34, 30, "抓到旗子", LIME, 16)
        if self.scene == "piano":
            for tx, ty, hi in self.tips:
                px = int(tx / 1280.0 * scr.lw)
                py = GROUND - 34
                col = CYAN if hi == 0 else YELLOW
                scr.rect(px - 2, py, 5, 5, col)
                scr.rect(px - 1, py + 5, 3, 6, col)
        if self.fail > 0:
            scr.frame(0, 0, scr.lw, STAGE_H, RED, 2)
        if self.msg_t > 0 and self.gate_msg:
            col = LIME if self.fail <= 0 else RED
            scr.text(AV_X - 28, 48, self.gate_msg, col, 13)
        acc = accent_of(self.scene)
        # challenge banner
        scr.window(2, 2, scr.lw - 4, 18, acc, NIGHT, 255)
        scr.text(6, 3, f"{self.act['name']}  {self.act.get('goal', '')}", acc, 13)
        bx = scr.lw - 116
        scr.seg_bar(bx, 6, 74, 9, self.frac, LIME if self.done else acc, seg=5)
        scr.pf(bx + 78, 7, self.text.split()[0] if self.text else "", WHITE, 1)
        scr.text(6, 22, self.text, WHITE, 11)
        if self.pop > 0:
            scr.text(scr.lw // 2 - 14, 36, "+1", LIME, 16)
        if self.done:
            scr.text(scr.lw // 2 - 30, 44, "挑战完成", LIME, 20)
