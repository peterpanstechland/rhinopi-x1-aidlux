# 模型广场目录（QCS8550 / X1）

从 [模型广场](https://aiot.aidlux.com/zh/models) 和板上 `mms list` 整理。浏览免登录，下载需要阿加犀开发者账号。

官方卡上的「推理耗时」不含前后处理。我们的 e2e FPS 不要和它直接对打。

## 联调板上已有的 QCS8550 模型

路径：`/usr/local/share/aidstream-gst/example/datas/`

| 文件 | 芯片 | 精度 | QNN | 来源 |
| --- | --- | --- | --- | --- |
| `cutoff_yolov5s_sigmoid_qcs8550_w8a8.qnn236.ctx.bin` | QCS8550 | W8A8 | 2.36 | AidStream 示例，已在板 |
| `cutoff_yolov8s_qcs8550_fp16.qnn231.ctx.bin` | QCS8550 | FP16 | 2.31 | 同上 |
| `cutoff_yolov8s-seg_qcs8550_fp16.qnn236.ctx.bin` | QCS8550 | FP16 | 2.36 | 同上 |
| `cutoff_yolov5s_sigmoid_qcs6490_w8a8.qnn236.ctx.bin` | QCS6490 | W8A8 | 2.36 | A1 用，X1 不要拿来当主测 |

## 待 `mms list` 补全

需要模型广场账号后执行：

```bash
mms login
mms list yolo
mms list pose
```

把芯片为 Qualcomm QCS8550 的行贴到下面。

| 模型 | 精度 | QNN | 官方纯推理 | 我们实测纯推理 | 下载通道 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  | 网页 / MMS / 预览 |  |

主线第一只检测模型：优先能直接下到的 YOLOv5s 或 YOLOv8s / YOLOv11n（QCS8550 + INT8）。联调板已有 YOLOv5s W8A8 QNN236，可先用来打通 AidLite。
