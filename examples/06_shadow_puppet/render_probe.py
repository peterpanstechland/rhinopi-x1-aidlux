#!/usr/bin/env python3
"""Render every screen with a synthetic pose so layout can be checked offline.

python3 render_probe.py --out /tmp/ui
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "04_mediapipe"))

from gestures import Motion  # noqa: E402
from loop import ACTS, ALERT, AWAY, CLEAR, MONITOR, PLAY, READY, ROUND, SUMMARY, ActResult, DeskGame  # noqa: E402
from overlay import draw_screen  # noqa: E402
from pose_tracker import PoseResult  # noqa: E402
from posture import PostureWatch  # noqa: E402
from puppet import PixelPuppet  # noqa: E402
from scenes import Stage  # noqa: E402


def fake_pose(arms: str = "out") -> PoseResult:
    xy = np.zeros((31, 2), np.float32)
    vis = np.full(31, 0.9, np.float32)
    xy[0] = (640, 210)
    xy[1] = (620, 200)
    xy[2] = (612, 200)
    xy[3] = (604, 202)
    xy[4] = (660, 200)
    xy[5] = (668, 200)
    xy[6] = (676, 202)
    xy[7] = (592, 214)
    xy[8] = (688, 214)
    xy[9] = (626, 240)
    xy[10] = (654, 240)
    xy[11] = (540, 330)
    xy[12] = (740, 330)
    if arms == "out":
        xy[13] = (450, 350)
        xy[14] = (830, 350)
        xy[15] = (360, 330)
        xy[16] = (920, 330)
    elif arms == "up":
        xy[13] = (500, 260)
        xy[14] = (780, 260)
        xy[15] = (520, 150)
        xy[16] = (760, 150)
    else:
        xy[13] = (510, 440)
        xy[14] = (770, 440)
        xy[15] = (545, 540)
        xy[16] = (735, 540)
    xy[23] = (565, 620)
    xy[24] = (715, 620)
    return PoseResult(True, xy, vis, 92.0)


class FakeHands:
    class H:
        def __init__(self, x, y):
            self.xy = np.zeros((21, 2), np.float32)
            self.xy[:, 0] = x
            self.xy[:, 1] = y
            self.xy[8] = (x, y + 40)
            self.xy[5] = (x - 20, y)
            self.xy[17] = (x + 20, y)

        @property
        def span(self):
            return 40.0

    def __init__(self):
        self.hands = [self.H(430, 520), self.H(860, 520)]
        self.infer_ms = 38.0


NPU = {"ok": True, "ms": 9.4, "err": "", "thermal": {"nspss-0": 41.0, "cpuss-0": 52.0, "gpuss-0": 38.0}}


def base_frame() -> np.ndarray:
    img = np.zeros((720, 1280, 3), np.uint8)
    img[:] = (70, 62, 58)
    for y in range(0, 720, 40):
        img[y : y + 20] = (92, 82, 76)
    cv2.putText(img, "CAMERA", (430, 380), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (160, 160, 160), 6)
    return img


def make_posture(score: float, title: str = "低头前伸") -> dict:
    return {
        "score": score,
        "avg": score,
        "grade": "S" if score > 88 else ("A" if score > 76 else ("B" if score > 62 else "C")),
        "bad": score < 62,
        "bad_s": 30.0,
        "bad_total": 240.0,
        "worst": "neck",
        "title": title if score < 78 else "",
        "advice": "把下巴收回来，屏幕抬高一点",
        "tracked": True,
        "nudge_hold": 0.0,
        "nudge": "",
    }


def shot(out: Path, name: str, game, stage, puppet, motion, pose, posture, hands=None):
    frame = base_frame()
    canvas = draw_screen(
        frame, game, stage, puppet, motion, pose, 11.4, 92.0, NPU, posture, hands
    )
    path = out / f"{name}.jpg"
    cv2.imwrite(str(path), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    print("wrote", path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/ui")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    game = DeskGame(interval=1200, round_len=6, path=out / "probe_save.json")
    game.reset_day()
    puppet = PixelPuppet()
    stage = Stage()

    pose_out = fake_pose("out")
    pose_up = fake_pose("up")
    pose_down = fake_pose("down")

    # sit-watch screens
    game.phase = MONITOR
    game.present = True
    game.sit_s = 640.0
    puppet.update(pose_down, 0.1)
    shot(out, "01_monitor", game, stage, puppet, Motion(), pose_down, make_posture(84, ""))
    shot(out, "02_monitor_bad", game, stage, puppet, Motion(), pose_down, make_posture(41))
    game.phase = ALERT
    game.sit_s = 1290.0
    shot(out, "03_alert", game, stage, puppet, Motion(), pose_down, make_posture(52))
    game.phase = AWAY
    game.present = False
    shot(out, "04_away", game, stage, puppet, Motion(), PoseResult(False, np.zeros((31, 2)), np.zeros(31), 33.0), make_posture(70))

    # round screens, one per act
    game.present = True
    game.phase = ROUND
    game.acts = list(ACTS)
    game.round_time = 34.0
    game.combo = 3
    game.score = 4260
    hands = FakeHands()
    for i, act in enumerate(ACTS):
        game.act_i = i
        stage.begin(act)
        stage.got = stage.need * 0.6
        if act["scene"] == "turn":
            stage.left_got, stage.right_got = 3, 2
            stage.got = 2
        if act["scene"] == "ski":
            stage.gates = [
                {"x": 134.0, "y": 34.0, "kind": "flag", "state": 0},
                {"x": 212.0, "y": 62.0, "kind": "tree", "state": 0},
                {"x": 160.0, "y": 92.0, "kind": "flag", "state": 1},
                {"x": 108.0, "y": 14.0, "kind": "tree", "state": 0},
            ]
            stage.gate_msg = "碰到旗子"
            stage.msg_t = 1.0
            stage.avatar_dx = 0.0
        if act["scene"] == "piano":
            stage.keys_lit = {3: 1.0, 9: 0.6}
            stage.notes = [[70.0, 70.0], [210.0, 58.0]]
            stage.finger_press = [0, 0, 0.9, 0, 0, 0, 0, 0.4, 0, 0]
        if act["scene"] == "wave":
            stage.got = 6
            stage.sign = 1.0
            stage.gate_msg = "再见！"
            stage.msg_t = 1.0
            stage.pop = 0.3
        if act["scene"] == "eagle":
            stage.alt = 32.0
            stage.scroll = 48.0
            stage.wing_beat = 0.75
            stage.avatar_dy = -3.0
        pose = pose_up if act["scene"] == "dino" else (pose_out if act["scene"] in ("wings", "eagle", "wave") else pose_down)
        puppet.have = False
        puppet.update(pose, 0.1)
        m = Motion(
            wings=0.9,
            flap=0.6,
            wave=0.7,
            lean=0.5,
            lean_dir=0.6,
            piano=0.7,
            piano_lx=0.38,
            piano_rx=0.64,
            hands_up=0.8,
            turn=0.7,
            turn_dir=-0.7,
        )
        game.sub = PLAY
        stage.step(m, hands, 0.05, False)
        shot(out, f"10_act_{act['scene']}", game, stage, puppet, m, pose, make_posture(80, ""), hands)

    # ready + clear cards
    game.act_i = 0
    stage.begin(ACTS[0])
    game.sub = READY
    game.t_state = 0.6
    shot(out, "20_ready", game, stage, puppet, Motion(), pose_out, make_posture(80, ""))
    game.results = [ActResult(ACTS[0], True, 6.2, "A", 180)]
    game.sub = CLEAR
    game.t_state = 0.5
    shot(out, "21_clear", game, stage, puppet, Motion(), pose_out, make_posture(80, ""))

    # summary
    game.results = [
        ActResult(ACTS[0], True, 5.1, "S", 220),
        ActResult(ACTS[1], True, 11.4, "A", 180),
        ActResult(ACTS[2], True, 8.0, "S", 240),
        ActResult(ACTS[3], False, 22.0, "-", 0),
        ActResult(ACTS[4], True, 18.2, "B", 150),
        ActResult(ACTS[5], True, 7.7, "S", 260),
    ]
    game.round_score = 1250
    game.rounds = 4
    game.streak = 2
    game.best_combo = 5
    game.sit_day = 5400.0
    game.phase = SUMMARY
    shot(out, "30_summary", game, stage, puppet, Motion(), pose_out, make_posture(73, "低头前伸"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
