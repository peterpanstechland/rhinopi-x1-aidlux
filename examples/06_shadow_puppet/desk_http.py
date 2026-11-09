"""Local assets, game telemetry and MJPEG for the X1 browser clients."""

from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import cv2

WEB_ROOT = Path(__file__).resolve().with_name("web")
PREVIEW_HTML = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>姿态预览 · AidLite Pose</title>
<style>body{margin:0;background:#101322;color:#ebfff7;font:16px system-ui}
main{max-width:1280px;margin:2rem auto;padding:0 1rem}img{width:100%;height:auto}</style>
<main><h1>姿态预览</h1><img src="/stream" alt="摄像头画面与姿态骨架"></main></html>"""


class JpegHub:
    def __init__(self) -> None:
        self._buf = b""
        self._changed = threading.Condition()

    def update(self, bgr) -> None:
        ok, enc = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        if ok:
            with self._changed:
                self._buf = enc.tobytes()
                self._changed.notify_all()

    def next_frame(self, previous: bytes) -> bytes:
        with self._changed:
            self._changed.wait_for(lambda: self._buf is not previous, timeout=1)
            return self._buf


class StatusHub:
    def __init__(self) -> None:
        self._data: dict = {}
        self._lock = threading.Lock()

    def update(self, data: dict) -> None:
        with self._lock:
            self._data = dict(data)

    def latest(self) -> dict:
        with self._lock:
            return dict(self._data)


def start_http(hub: JpegHub, status: StatusHub | None, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def reply(self, content_type: str, body: bytes):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command == "HEAD":
                return
            previous = b""
            try:
                while not server_closed.is_set():
                    frame = hub.next_frame(previous)
                    if frame and frame is not previous:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                    previous = frame
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/stream":
                self.stream()
                return
            if path == "/status" and status is not None:
                body = json.dumps(status.latest(), ensure_ascii=False).encode("utf-8")
                self.reply("application/json; charset=utf-8", body)
                return
            if status is None:
                if path == "/":
                    self.reply("text/html; charset=utf-8", PREVIEW_HTML.encode("utf-8"))
                else:
                    self.send_error(404)
                return

            relative = "index.html" if path == "/" else path.lstrip("/")
            if any(part.startswith(".") for part in relative.split("/")) or any(c in relative for c in "\\\x00:"):
                self.send_error(404)
                return
            try:
                file = (WEB_ROOT / relative).resolve()
                if not file.is_relative_to(WEB_ROOT) or not file.is_file():
                    self.send_error(404)
                    return
                body = file.read_bytes()
                if file == WEB_ROOT / "index.html":
                    body = body.replace(b'data-device="arcade"', b'data-device="board"', 1)
            except (OSError, ValueError):
                self.send_error(404)
                return
            content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            if file.suffix == ".js":
                content_type = "text/javascript"
            self.reply(content_type, body)

    server_closed = threading.Event()

    class Server(ThreadingHTTPServer):
        def server_close(self):
            server_closed.set()
            super().server_close()

    httpd = Server((host, port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
