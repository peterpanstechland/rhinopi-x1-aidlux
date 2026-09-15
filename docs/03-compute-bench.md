# 算力与系统体检

确认 CPU 和 NPU 都能用，并留下可对比的数字。这不是跑分软件。

## 目标

- 留下系统快照（版本、内存、温度）
- 同一输入尺寸（默认 640）下测 numpy / OpenCV / NPU
- 报表字段和后面的 MediaPipe / YOLO 章对齐

## 相关资料

- [AidLite SDK](https://developer.aidlux.com/software/aidlite)
- [软件指南 · AidLite](https://docs.aidlux.com/software/)

## 在板子上跑

```bash
cd ~/rhinopi-lab/examples/02_compute_bench
python3 bench.py
```

NPU 默认用板上自带的 YOLOv5s QNN236 量化模型，加速类型 `TYPE_DSP`。

## 统一报表字段

每一项都记：输入分辨率、后端、平均 / 最小 / 最大耗时（毫秒）、循环次数、温度。

NPU 一项明确写清：是否包含前后处理。模型广场卡片上的延迟 **不含** 前后处理。

## 联调板数字（2026-09-14）

`python3 bench.py`，640 输入，warmup 5 + 20 次：

- numpy：平均 15.8 ms
- OpenCV 预处理（1280×720 → 640 + blur）：平均 3.4 ms
- YOLOv5s W8A8 + AidLite QNN236 + DSP：平均 **4.77 ms**（约 210 inf/s），min/max 4.63 / 4.97 ms

这是 `set_input + invoke + get_output`，没有 YOLO 后处理。和模型广场卡片比时，先对齐「是否含前后处理」。完整 JSON 在 [实测记录](experience-log.md)。

## 本步验收

- `check_env.py` 与 `bench.py` 都能跑完
- NPU 一项不是 FAIL（除非模型文件被删）
- 数字已记进实测记录

## 拍照点

见 [拍照清单](photo-checklist.md) 第 3 组。
