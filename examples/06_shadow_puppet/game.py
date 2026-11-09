#!/usr/bin/env python3
"""Desk-break stretch game: upper-body only, stick figure + activity points."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "04_mediapipe"))
sys.path.insert(0, str(ROOT / "usb_camera"))
sys.path.insert(0, str(ROOT / "06_shadow_puppet"))

from camera import open_usb  # noqa: E402
from desk_http import JpegHub, StatusHub, start_http  # noqa: E402
from gestures import GestureTracker  # noqa: E402
from loop import ACTS, PLAY, ROUND, SUMMARY, DeskGame  # noqa: E402
from overlay import draw_hands, draw_screen, draw_stick  # noqa: E402
from pixel_ui import LIME, RED, YELLOW, scanlines  # noqa: E402
from pose_tracker import PoseResult, PoseTracker  # noqa: E402
from posture import PostureWatch  # noqa: E402
from puppet import PixelPuppet  # noqa: E402
from scenes import Stage  # noqa: E402
from stats import DeadPulse, NpuPulse  # noqa: E402


def pose_points(pose: PoseResult | None, frame_shape: tuple) -> list[list[float] | None]:
    """Project just the nose and arm joints in mirrored camera coordinates."""
    if pose is None or not pose.ok:
        return []
    height, width = frame_shape[:2]
    points: list[list[float] | None] = [None] * 25
    available = min(len(pose.xy), len(pose.vis))
    for index in (0, 11, 12, 13, 14, 15, 16):
        if index >= available:
            continue
        x, y = pose.xy[index]
        if pose.vis[index] >= 0.25 and 0 <= x < width and 0 <= y < height:
            points[index] = [round(float(x) / width, 4), round(float(y) / height, 4)]
    return points


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=None)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--save", default="")
    parser.add_argument("--accel", default="GPU", choices=("GPU", "CPU", "DSP"))
    parser.add_argument("--no-npu", action="store_true")
    parser.add_argument("--interval-min", type=float, default=25.0, help="久坐提醒间隔，默认 25 分钟")
    parser.add_argument("--demo", action="store_true", help="45 秒间隔，用来快速走完一局")
    parser.add_argument("--round-acts", type=int, default=6, help="一回合几个动作")
    parser.add_argument("--no-scanlines", action="store_true")
    parser.add_argument("--reset", action="store_true", help="清空当天进度，录像前用")
    args = parser.parse_args()

    print("loading upper-body Pose...", flush=True)
    tracker = PoseTracker(accel=args.accel, full_body=False, selfie=True)
    npu = DeadPulse() if args.no_npu else NpuPulse()
    print("npu", "ok" if npu.ok else getattr(npu, "err", "off"), flush=True)
    cap = open_usb(args.index, args.width, args.height)
    ok, first = cap.read()
    pose = tracker.infer(cv2.flip(first, 1)) if ok and first is not None else None
    hub = JpegHub()
    status = StatusHub()
    interval = 45.0 if args.demo else max(30.0, args.interval_min * 60.0)
    game = DeskGame(interval=interval, round_len=min(len(ACTS), max(2, args.round_acts)))
    if args.reset or args.demo:
        game.reset_day()
    print(f"sit interval {game.interval:.0f}s  acts={game.round_len}  phase={game.phase}", flush=True)
    gest = GestureTracker()
    stage = Stage()
    stage.begin(game.act)
    puppet = PixelPuppet()
    watch = PostureWatch()
    status.update({
        **game.snapshot(),
        "camera_online": pose is not None,
        "pose_aspect": round(first.shape[1] / first.shape[0], 4) if pose is not None else None,
        "pose_points": pose_points(pose, first.shape) if pose is not None else [],
        "posture": watch.snapshot(),
        "challenge": stage.challenge_snapshot(include_visual=game.phase == ROUND),
    })
    server = None if args.no_web else start_http(hub, status, args.host, args.port)
    if server:
        print(f"HTTP listening on {args.host}:{server.server_port}", flush=True)
    hand_tracker = None
    hands = None
    t_end = time.perf_counter() + args.seconds if args.seconds else None
    last = time.perf_counter()
    last_canvas = None
    frames = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                snap = status.latest()
                if snap["camera_online"]:
                    # Discard motion accumulated before the camera dropped. Start the
                    # next detection from its own baseline, preserving completed nods.
                    gest = GestureTracker(nod_count=gest.nod_count)
                    stage.tracking = False
                    stage.feedback = None
                    stage.press_base.clear()
                    status.update({**snap, "camera_online": False, "pose_points": [],
                                   "challenge": stage.challenge_snapshot(include_visual=game.phase == ROUND)})
                if t_end and time.perf_counter() >= t_end:
                    if frames == 0:
                        print("No camera frames received.", file=sys.stderr)
                        return 1
                    break
                time.sleep(0.05)
                last = time.perf_counter()
                continue
            frame = cv2.flip(frame, 1)
            want_hands = game.needs_hands and game.sub == PLAY
            if want_hands and hand_tracker is None:
                try:
                    from hand_tracker import HandTracker

                    print("loading hand landmarks...", flush=True)
                    hand_tracker = HandTracker(accel=args.accel)
                except Exception as exc:  # noqa: BLE001
                    print("hand tracker off:", exc, flush=True)
                    hand_tracker = False
            t_pose = time.perf_counter()
            # the piano act is driven by fingertips, so pose can run at 1/3 rate
            if not (want_hands and hand_tracker) or frames % 3 == 0:
                pose = tracker.infer(frame)
            t_pose = (time.perf_counter() - t_pose) * 1000
            t_hand = 0.0
            if want_hands and hand_tracker:
                t_hand = time.perf_counter()
                hands = hand_tracker.infer(frame)
                t_hand = (time.perf_counter() - t_hand) * 1000
            elif not want_hands:
                hands = None
            npu.tick(frame)
            now = time.perf_counter()
            dt = max(now - last, 1e-3)
            last = now
            frames += 1
            motion = gest.update(pose, frame.shape)
            reading = watch.step(pose, frame.shape, dt, active=game.phase not in (ROUND, SUMMARY))
            live = game.phase == ROUND and game.sub == PLAY
            stage.frame_width = frame.shape[1]
            stage.piano_input = "wrists" if hand_tracker is False else "fingers"
            stage.step(motion, hands, dt, live)
            puppet.update(pose, dt)
            game.step(
                motion,
                dt,
                pose.ok,
                reading.score if reading.ok else None,
                stage.frac,
                posture_bad=bool(watch.bad),
            )
            for ev in game.pop_events():
                if ev == "round_end":
                    watch.recalibrate()
                elif ev == "act_begin":
                    stage.begin(game.act)
            t_ui = time.perf_counter()
            posture = watch.snapshot()
            posture["nudge_hold"] = watch.nudge_hold
            posture["nudge"] = watch.nudge
            stick = LIME
            if posture.get("tracked") and posture["score"] < 60:
                stick = RED
            elif posture.get("tracked") and posture["score"] < 78:
                stick = YELLOW
            if not args.no_scanlines and game.phase not in (ROUND, SUMMARY):
                scanlines(frame)
            draw_stick(frame, pose, stick)
            if hands is not None:
                draw_hands(frame, hands)
            canvas = draw_screen(
                frame,
                game,
                stage,
                puppet,
                motion,
                pose,
                1.0 / dt,
                pose.infer_ms,
                npu.snapshot(),
                posture,
                hands,
                nod_dipped=gest.nod_dipped,
            )
            t_ui = (time.perf_counter() - t_ui) * 1000
            t_enc = time.perf_counter()
            hub.update(canvas)
            t_enc = (time.perf_counter() - t_enc) * 1000
            snap = game.snapshot()
            snap["camera_online"] = True
            snap["pose_aspect"] = round(frame.shape[1] / frame.shape[0], 4)
            snap["pose_points"] = pose_points(pose, frame.shape)
            snap["posture"] = posture
            snap["challenge"] = stage.challenge_snapshot(
                include_visual=game.phase == ROUND, motion=motion, nod_dipped=gest.nod_dipped
            )
            status.update(snap)
            last_canvas = canvas
            if frames % 20 == 0:
                npu_s = npu.snapshot()
                print(
                    f"frame {frames} fps={1.0 / dt:.1f} pose={pose.ok} {t_pose:.0f}ms "
                    f"hand={t_hand:.0f}ms ui={t_ui:.0f}ms enc={t_enc:.0f}ms "
                    f"phase={snap['phase']}/{snap['sub']} act={snap['act']} "
                    f"chal={stage.text} left={snap['round_left']:.0f}s "
                    f"sit={snap['sit_s']:.0f}s score={snap['score']} "
                    f"posture={posture['score']:.0f} npu={npu_s.get('ms', 0):.1f}ms",
                    flush=True,
                )
            if t_end and now >= t_end:
                break
    except KeyboardInterrupt:
        print("stop")
    finally:
        if server:
            server.shutdown()
            server.server_close()
        game.save()
        cap.release()
        if args.save and last_canvas is not None:
            out = Path(args.save)
            out.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out), last_canvas)
            print("saved", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
