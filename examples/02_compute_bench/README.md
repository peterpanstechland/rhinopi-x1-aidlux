# 算力体检

在板子上跑 CPU（numpy）、OpenCV 预处理、以及板上自带的 YOLOv5s QNN236 NPU 循环。

```bash
python3 bench.py
python3 bench.py --skip-npu          # 只要 CPU / OpenCV
python3 bench.py --loops 50 --warmup 10
```

默认模型：

`/usr/local/share/aidlite/examples/aidlite_qnn236/data/qnn_yolov5_multi/cutoff_yolov5s_640_sigmoid_w8a8.qnn236.ctx.bin`

NPU 数字是 `set_input + invoke + get_output`，不含 YOLO 后处理，便于和模型广场「纯推理耗时」对照。
