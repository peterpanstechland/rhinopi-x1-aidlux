#!/usr/bin/env python3
"""CPU / OpenCV / NPU micro-benchmark on Rhino Pi X1."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np

DEFAULT_QNN_MODEL = (
    "/usr/local/share/aidlite/examples/aidlite_qnn236/data/"
    "qnn_yolov5_multi/cutoff_yolov5s_640_sigmoid_w8a8.qnn236.ctx.bin"
)
DEFAULT_IMAGE = (
    "/usr/local/share/aidlite/examples/aidlite_qnn236/data/qnn_yolov5_multi/bus.jpg"
)


def timed_loop(fn, loops: int, warmup: int) -> dict:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(loops):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return {
        "loops": loops,
        "warmup": warmup,
        "avg_ms": round(statistics.mean(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "stdev_ms": round(statistics.pstdev(samples), 3) if len(samples) > 1 else 0.0,
    }


def bench_cpu(size: int, loops: int, warmup: int) -> dict:
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, size=(size, size, 3), dtype=np.uint8).astype(np.float32) / 255.0
    mat = rng.standard_normal((size, size), dtype=np.float32)

    def work():
        a = img * 1.0
        b = a.mean(axis=2)
        _ = mat @ mat[:size, :size]

    return {"backend": "numpy", "input": f"{size}x{size}", **timed_loop(work, loops, warmup)}


def bench_opencv(size: int, loops: int, warmup: int) -> dict:
    import cv2

    rng = np.random.default_rng(1)
    img = rng.integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)

    def work():
        resized = cv2.resize(img, (size, size))
        _ = cv2.GaussianBlur(resized, (5, 5), 0)

    return {"backend": "opencv", "input": f"{size}x{size}", **timed_loop(work, loops, warmup)}


def letterbox(image, size: int):
    import cv2

    h, w, _ = image.shape
    mask = np.zeros((size, size, 3), dtype=np.float32)
    scale = max(h / size, w / size)
    nh, nw = int(h / scale), int(w / scale)
    img = cv2.resize(image, (nw, nh))
    mask[:nh, :nw, :] = img
    return mask


def bench_npu(model_path: str, image_path: str, loops: int, warmup: int) -> dict:
    import cv2
    import aidlite

    model = aidlite.Model.create_instance(model_path)
    if model is None:
        raise RuntimeError(f"create model failed: {model_path}")

    config = aidlite.Config.create_instance()
    if config is None:
        raise RuntimeError("create config failed")
    config.framework_type = aidlite.FrameworkType.TYPE_QNN236
    config.accelerate_type = aidlite.AccelerateType.TYPE_DSP

    interpreter = aidlite.InterpreterBuilder.build_interpreter_from_model_and_config(model, config)
    if interpreter is None:
        raise RuntimeError("build interpreter failed")
    if interpreter.init() != 0:
        raise RuntimeError("interpreter.init failed")
    if interpreter.load_model() != 0:
        raise RuntimeError("load_model failed")

    frame = cv2.imread(image_path)
    if frame is None:
        raise RuntimeError(f"cannot read image: {image_path}")
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img_input = (letterbox(rgb, 640) / 255.0).astype(np.float32)

    input_info = interpreter.get_input_tensor_info()
    in_name = input_info[0][0].name
    out_info = interpreter.get_output_tensor_info()
    out_names = [t.name for g in out_info for t in g]

    def work():
        if interpreter.set_input_tensor(in_name, img_input.data) != 0:
            raise RuntimeError("set_input_tensor failed")
        if interpreter.invoke() != 0:
            raise RuntimeError("invoke failed")
        for name in out_names:
            if interpreter.get_output_tensor(name) is None:
                raise RuntimeError(f"get_output_tensor failed: {name}")

    stats = timed_loop(work, loops, warmup)
    interpreter.destroy()
    return {
        "backend": "aidlite_qnn236_dsp",
        "model": model_path,
        "image": image_path,
        "input": "640x640",
        "note": "set_input + invoke + get_output; no YOLO postprocess",
        **stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--loops", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--skip-npu", action="store_true")
    parser.add_argument("--model", default=DEFAULT_QNN_MODEL)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    args = parser.parse_args()

    report = {
        "cpu_numpy": bench_cpu(args.size, args.loops, args.warmup),
        "opencv_preprocess": bench_opencv(args.size, args.loops, args.warmup),
    }

    if not args.skip_npu:
        if not Path(args.model).exists():
            report["npu"] = {"ok": False, "error": f"model not found: {args.model}"}
        else:
            try:
                report["npu"] = {"ok": True, **bench_npu(args.model, args.image, args.loops, args.warmup)}
            except Exception as exc:  # noqa: BLE001
                report["npu"] = {"ok": False, "error": str(exc)}

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\n=== summary (avg_ms) ===")
    for key in ("cpu_numpy", "opencv_preprocess"):
        print(f"{key:20} {report[key]['avg_ms']} ms")
    npu = report.get("npu")
    if npu:
        if npu.get("ok"):
            print(f"{'npu_yolov5s_dsp':20} {npu['avg_ms']} ms  ({1000.0 / npu['avg_ms']:.1f} inf/s)")
        else:
            print(f"{'npu':20} FAIL  {npu.get('error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
