"""Exercise camera-space trajectories through the same recognizer and stage used by game.py."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "04_mediapipe"))

from gestures import GestureTracker
from loop import ACT_BY_ID
from pose_tracker import PoseResult
from scenes import Stage, SKI_HIT_Y


def pose(nose=(320, 115), left=(250, 285), right=(390, 285), lift=0):
    xy = np.zeros((31, 2), np.float32)
    vis = np.zeros(31, np.float32)
    joints = {0: nose, 7: (294, 115), 8: (346, 115), 11: (270, 200), 12: (370, 200), 15: left, 16: right}
    for index, point in joints.items():
        if point is not None:
            xy[index] = (point[0], point[1] + lift)
            vis[index] = 1
    return PoseResult(True, xy, vis, 30)


class ActionMatch(unittest.TestCase):
    def start(self, action):
        self.gest = GestureTracker()
        self.stage = Stage()
        self.stage.begin(ACT_BY_ID[action])

    def feed(self, frame, n=1, hands=None):
        for _ in range(n):
            motion = self.gest.update(frame, (480, 640, 3))
            self.stage.step(motion, hands, 0.1, True)
        return self.stage.challenge_snapshot(include_visual=True)

    def test_hold_requires_both_wrist_tracks(self):
        self.start("wings")
        self.feed(pose(left=(155, 200)), 30)
        self.assertEqual(self.stage.got, 0)
        self.feed(pose(left=(155, 200), right=(485, 200)), 20)
        count = self.stage.got
        self.assertGreater(count, 1)
        status = self.feed(pose(left=None, right=(485, 200)), 30)
        self.assertFalse(status["tracking"])
        self.assertFalse(self.feed(pose(left=(-20, 200), right=(485, 200)))["tracking"])
        self.assertEqual(self.stage.got, count)
        self.assertTrue(self.feed(pose(left=(155, 200), right=(485, 200)), 45)["frac"] == 1)

    def test_eagle_counts_full_spread_flaps(self):
        self.start("flap")
        for _ in range(4):
            for y in (200, 160, 200):
                self.feed(pose(left=(260, y), right=(380, y)))
        self.assertEqual(self.stage.got, 0)
        for _ in range(4):
            for lift in (0, -30, 0):
                self.feed(pose(left=(155, 200), right=(485, 200), lift=lift))
        self.assertEqual(self.stage.got, 0)
        for _ in range(4):
            for y in (200, 160, 200):
                self.feed(pose(left=(155, y), right=(485, 200 + (y - 200) * 0.03)))
        self.assertEqual(self.stage.got, 0)
        for _ in range(8):
            for y in (200, 160, 200):
                self.feed(pose(left=(155, y), right=(485, y)))
        self.assertEqual(self.stage.got, 8)

    def test_wave_one_raised_hand_can_play(self):
        self.start("wave")
        for x in (210, 250, 210, 250):
            self.feed(pose(left=(x, 270), right=None))
        self.assertEqual(self.stage.got, 0)
        for x in (210, 250, 210, 250, 210):
            self.feed(pose(left=(x, 170), right=None))
        self.assertEqual(self.stage.got, 4)

    def test_turn_and_nod_with_wrists_out_of_view(self):
        self.start("turn")
        for _ in range(3):
            for x in (320, 285, 320, 355):
                self.feed(pose(nose=(x, 115), left=None, right=None), 8)
        status = self.stage.challenge_snapshot(include_visual=True)
        self.assertEqual((status["count"], status["target"], status["frac"]), (6, 6, 1))
        self.start("nod")
        for lift in (0, 18, 0, 20, 0):
            self.feed(pose(lift=lift))
        self.assertEqual(self.stage.got, 0)
        self.feed(pose(left=None, right=None))
        for _ in range(6):
            self.feed(pose(nose=(320, 133), left=None, right=None), 4)
            self.feed(pose(nose=(320, 115), left=None, right=None), 4)
        self.assertEqual(self.stage.got, 6)

    def test_ski_collision_requires_tracking(self):
        self.start("lean")
        self.stage.gates = [dict(x=160, y=SKI_HIT_Y - 4, kind="flag", state=0)]
        self.feed(pose(nose=None), 20)
        self.assertEqual(self.stage.got, 0)
        status = self.feed(pose(left=None, right=None))
        self.assertEqual(status["feedback"]["kind"], "hit")
        self.stage.gates = [dict(x=160, y=SKI_HIT_Y - 4, kind="tree", state=0)]
        status = self.feed(pose(left=None, right=None))
        self.assertEqual((status["count"], status["feedback"]["kind"]), (0, "miss"))

    def test_dino_rearms_after_shoulder_return(self):
        self.start("hands_up")
        pulses = [
            self.gest.update(pose(lift=dy, left=None, right=None)).jump
            for dy in (0, -10, -10, -22, 0, 0, -10)
        ]
        self.assertEqual(pulses, [0, 1, 0, 0, 0, 0, 1])
        self.stage.obs = 191
        for dy in (0, 0, -16, 0, *([0] * 16)):
            self.feed(pose(lift=dy, left=None, right=None))
        self.assertEqual(self.stage.got, 1)

    def test_piano_fingers_and_wrist_fallback(self):
        self.start("piano")
        self.stage.frame_width = 640
        self.stage.target_key = 8
        tips = np.array([[390 + i * 10, 215] for i in range(5)])
        hands = SimpleNamespace(hands=[SimpleNamespace(wrist=(410, 235), span=50, tips=tips)])
        self.feed(pose(), hands=hands)
        tips[2, 1] += 18
        self.assertEqual(self.feed(pose(), hands=hands)["feedback"]["kind"], "miss")
        tips[2, 1] -= 18
        self.feed(pose(), hands=hands)
        tips[3, 1] += 18
        self.feed(pose(), 7, hands)
        self.assertEqual(self.stage.got, 1)
        self.assertFalse(self.feed(pose())["tracking"])
        self.start("piano")
        self.stage.piano_input = "wrists"
        for y in (200, 218, 200):
            self.feed(pose(left=(253, y), right=None))
        self.assertEqual(self.stage.got, 0)  # x=253 maps to 2, neighboring the target (3).
        for y in (200, 218, 218, 218):
            status = self.feed(pose(left=(282, y), right=None))
        self.assertEqual((status["count"], status["piano_input"]), (1, "wrists"))


if __name__ == "__main__":
    unittest.main()
