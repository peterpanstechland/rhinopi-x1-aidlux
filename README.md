# 犀牛派 X1 使用体验与教程

面向公开用户的 **犀牛派 X1（Qualcomm QCS8550）+ AidLux 融合系统** 上手教程：从刷机、登录、算力体检，到模型广场、MediaPipe / YOLO，再到工位回血（上半身活动积分），最后探索 CSI 等板级能力。

官方资料只作入口和对照，步骤、踩坑和实测以本仓库为准。

## 你要准备什么

- 犀牛派 X1，电源 DC 12V 5A
- Windows 电脑（刷机、ADB）；和板子同一局域网
- USB Type-A 转 Type-C 线、网线（推荐有线）
- USB 摄像头（主线演示）；CSI 模组放到后半段
- 可选：HDMI 显示器、键鼠

默认账号密码是 `aidlux` / `aidlux`。第一次登录后请改密码。

当前进度：工位回血（上半身活动积分）可在浏览器玩。

## 建议阅读顺序

1. [官方资料地图](docs/official-links.md)
2. [开箱与刷机](docs/01-unbox-and-flash.md)
3. [登录与环境](docs/02-login-and-env.md)
4. [算力与系统体检](docs/03-compute-bench.md)
5. [模型广场](docs/04-modelfarm.md)（撰写中）
6. [工位回血](docs/05-shadow-puppet.md)
7. 模型广场 / YOLO / CSI（后续章节）

配套清单：

- [拍照清单](docs/photo-checklist.md)
- [实测记录](docs/experience-log.md)
- [模型广场目录](docs/modelfarm-catalog.md)

## 示例代码

在板子 Ubuntu 侧运行：

| 目录 | 作用 | 状态 |
| --- | --- | --- |
| [examples/01_env_check](examples/01_env_check) | 系统、Python、AidLite、相机探测 | 已在联调板验证 |
| [examples/02_compute_bench](examples/02_compute_bench) | CPU / OpenCV / NPU 体检 | 已在联调板验证 |
| [examples/usb_camera](examples/usb_camera) | USB 节点识别、抓帧、MJPG 帧率 | 已在联调板验证 |
| [examples/03_modelfarm](examples/03_modelfarm) | 模型广场下载与官方包 | 待写 |
| [examples/04_mediapipe](examples/04_mediapipe) | AidLite Pose 预览（:8091） | 已在联调板验证 |
| [examples/05_yolo](examples/05_yolo) | 模型广场 YOLO + 相机 | 待写 |
| [examples/06_shadow_puppet](examples/06_shadow_puppet) | 工位回血：火柴人 + 活动积分 + NPU 底栏（:8090） | 已在联调板验证 |
| [examples/07_csi_camera](examples/07_csi_camera) | CSI 预览与接入 | 待写 |

约定：文档里标了「本机已验证」的命令，是在联调板上跑通过的；标「待实机」的还没跑。

## 本仓库联调板（2026-09-14）

- 地址：`192.168.88.216`（`eth0`）
- 系统：AidLux 融合系统，Ubuntu 22.04.2，内核 `5.15.178-android13`
- 账号：`aidlux` / `aidlux`
- Web 桌面：<http://192.168.88.216:8000/login>
- 2026-09-15 已重刷：Android `RhinoPi-X1.1.user.2026070119` + AidLux `3.0.0.124`
- 已预装 AidLite `2.3.2.251`、`aidlite-qnn236`、OpenCV `4.13.0`；尚未安装 MediaPipe
- USB：Logitech C920（`046d:082d`），采集 `/dev/video2`；1280×720 MJPG 约 30.5 fps。`video0/1/32/33` 是板载节点，不要当摄像头开

## 写法约定

- 下载工具看[开发者门户](https://developer.aidlux.com/software/debug_tool)
- 操作步骤看[文档中心](https://docs.aidlux.com/)；X1 专属优先 [犀牛派文档](https://rhinopi.docs.aidlux.com/rhino-x1-aidlux/)
- 排错可查[论坛](https://forum.aidlux.com/)，不整段转载
- 你拍的图放到 `docs/images/`，按[拍照清单](docs/photo-checklist.md)命名
