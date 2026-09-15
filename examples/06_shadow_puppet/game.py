#!/usr/bin/env python3
"""Desk-break stretch game: upper-body only, stick figure + activity points."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "04_mediapipe"))
sys.path.insert(0, str(ROOT / "usb_camera"))
sys.path.insert(0, str(ROOT / "06_shadow_puppet"))

from camera import open_usb  # noqa: E402
from gestures import GestureTracker  # noqa: E402
from loop import MONITOR, PLAY, ROUND, SUMMARY, DeskGame  # noqa: E402
from overlay import draw_hands, draw_screen, draw_stick  # noqa: E402
from pixel_ui import LIME, RED, YELLOW, scanlines  # noqa: E402
from pose_tracker import PoseTracker  # noqa: E402
from posture import PostureWatch  # noqa: E402
from puppet import PixelPuppet  # noqa: E402
from scenes import Stage  # noqa: E402
from stats import DeadPulse, NpuPulse  # noqa: E402


class JpegHub:
    def __init__(self) -> None:
        self._buf = b""
        self._lock = threading.Lock()

    def update(self, bgr) -> None:
        ok, enc = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        if not ok:
            return
        with self._lock:
            self._buf = enc.tobytes()

    def latest(self) -> bytes:
        with self._lock:
            return self._buf


class StatusHub:
    def __init__(self) -> None:
        self._d: dict = {}
        self._lock = threading.Lock()

    def update(self, data: dict) -> None:
        with self._lock:
            self._d = dict(data)

    def latest(self) -> dict:
        with self._lock:
            return dict(self._d)


def start_http(hub: JpegHub, status: StatusHub, host: str, port: int) -> ThreadingHTTPServer:
    page = """<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><title>工位回血</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Noto+Sans+SC:wght@700&display=swap" rel="stylesheet">
<style>
html,body{margin:0;background:#1a1c2c;color:#f4f4f4;text-align:center}
body{min-height:100vh;background-image:linear-gradient(#1a1c2c 50%,#14162a 50%);background-size:100% 4px}
.wrap{max-width:1280px;margin:0 auto;padding:18px 12px 28px}
.title{font-family:"Press Start 2P",monospace;color:#a7f070;font-size:18px;letter-spacing:2px;text-shadow:4px 4px 0 #1a1c2c,8px 8px 0 #b13e53}
.sub{font-family:"Noto Sans SC",sans-serif;color:#ffcd75;margin:14px 0 16px;font-size:16px}
.frame{display:inline-block;padding:6px;background:#ffcd75;box-shadow:0 0 0 4px #1a1c2c,0 0 0 8px #b13e53,0 0 0 12px #29366f}
.frame img{width:100%;max-width:1280px;display:block;background:#000;image-rendering:pixelated;image-rendering:crisp-edges}
.tip{font-family:"Noto Sans SC",sans-serif;color:#94b0c2;font-size:14px;line-height:1.8;margin-top:16px}
.hp{font-family:"Press Start 2P",monospace;color:#41a6f6;font-size:8px;margin-top:12px;letter-spacing:1px}
</style></head><body>
<div class="wrap">
<div class="title">HP REGEN</div>
<div class="sub">工位回血 · 久坐与坐姿监测</div>
<div class="frame"><img src="/stream" alt="desk-break"></div>
<div class="tip">静坐满 25 分钟催你回血；坐姿不对会额外扣血。一回合 6 个动作，每个动作一屏，做完自动跳下一个，最后出总结。<br>
平时右侧是坐姿评分：低头前伸、塌肩、歪肩、离屏太近都会扣分并掉血。举手可提前开回合。</div>
<div class="hp">SIT 25 MIN · BAD POSTURE DRAINS HP · 6 ACTS</div>
</div></body></html>"""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            if self.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    while True:
                        data = hub.latest()
                        if data:
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
                        time.sleep(0.03)
                except BrokenPipeError:
                    return
            if self.path.startswith("/status"):
                body = json.dumps(status.latest(), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))

    httpd = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


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
    if not args.no_web:
        start_http(hub, status, args.host, args.port)
        print(f"open  http://192.168.88.216:{args.port}/", flush=True)
    interval = 45.0 if args.demo else max(30.0, args.interval_min * 60.0)
    game = DeskGame(interval=interval, round_len=max(2, args.round_acts))
    if args.reset or args.demo:
        game.reset_day()
    print(f"sit interval {game.interval:.0f}s  acts={game.round_len}  phase={game.phase}", flush=True)
    gest = GestureTracker()
    stage = Stage()
    stage.begin(game.act)
    puppet = PixelPuppet()
    watch = PostureWatch()
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
            if not want_hands or frames % 3 == 0:
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
            motion = gest.update(pose)
            reading = watch.step(pose, frame.shape, dt, active=game.phase not in (ROUND, SUMMARY))
            live = game.phase == ROUND and game.sub == PLAY
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
            )
            t_ui = (time.perf_counter() - t_ui) * 1000
            t_enc = time.perf_counter()
            hub.update(canvas)
            t_enc = (time.perf_counter() - t_enc) * 1000
            snap = game.snapshot()
            snap["posture"] = posture
            snap["challenge"] = {"frac": round(stage.frac, 3), "text": stage.text}
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
