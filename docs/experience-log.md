# 实测记录

每台板子、每次镜像填一行。数字和版本以当场输出为准。

## 联调板 2026-09-14

| 项 | 值 |
| --- | --- |
| 角色 | 本仓库联调板，已初始化，**不要刷机** |
| IP | `192.168.88.216`（`eth0` /24） |
| 账号 | `aidlux` / `aidlux` |
| Web | `http://192.168.88.216:8000/login`（HTTP 200） |
| SSH | 22 开放，密码登录成功 |
| USB 序列号 | `FB803WFB5A300571` |
| 网络 ADB | `192.168.88.216:5555`（已连接） |
| Android 构建 | `RhinoPi-X1.1.user.2026070119` / `T04_LA_AL_SDK_V01.19b01` / Android 13 |
| 公开整包 | `RhinoPi-X1.T04_LA.user.2025121609.aidlux.zip`（比板上旧，刷会降级） |
| 公开 Android | `RhinoPi-X1.T04_LA.user.2026070119.zip`（与板上一致） |
| 公开 AidLux | `aidlux_3.0.0.124_enterprise_qc8550_lu2204_signed.zip` |
| 本机 QFIL | 未安装（2026-09-14） |
| 主机名 | `aidlux` |
| 内核 | `5.15.178-android13-8-gd05a78e066cd-dirty`，aarch64 |
| 用户态 | Ubuntu 22.04.2 LTS（Jammy），`ROOTFS_VERSION=92` |
| CPU | 6 核；最高约 3187 MHz / 2803 MHz / 2016 MHz 三丛集 |
| 内存 | 14 GiB 总计，体检时可用约 12 GiB |
| 磁盘 | userdata 79G，已用 57G（板子上已有课程目录、约 5GB + 4.8GB 压缩包） |
| Python | 3.10.12，`/usr/bin/python3` |
| pip | 26.0.1 |
| numpy | 1.26.4 |
| OpenCV | 4.13.0 |
| MediaPipe | 未安装 |
| AidLite | `Aidlux_Aidlite_P4L_V2.3.2.251_65129e3_20260410` |
| NPU 插件 | `aidlite-qnn236` 2.3.2.251 |
| 其他 SDK | `aidcv-sdk` 2.0.0，`aidstream-gst` 2.0.9，`aid-mms` 1.2.57，`aidgen-qnn236` / `qnn240` |
| 相机节点 | `/dev/video0` `video1` `video32` `video33` |
| USB 相机 | 未接入（只有 USB root hub） |
| 温度（空闲） | cpuss-0 约 39.4°C，nspss-0 约 34.1°C |
| 板上现成模型 | `/usr/local/share/aidstream-gst/example/datas/cutoff_yolov5s_sigmoid_qcs8550_w8a8.qnn236.ctx.bin` 等 |

### 刷机 2026-09-15

- 镜像：`RhinoPi-X1.T04_LA.user.2026070119`（仅 Android）+ AidLux `3.0.0.124`
- 方式：`adb reboot edl` → COM11 9008 → Sahara `xbl_s_devprg_ns.melf` → fh_loader 写 rawprogram/patch → reset
- 刷完 `ro.build.version.incremental` 仍为 `RhinoPi-X1.1.user.2026070119`
- AidLux：已 `adb push 0.deb`（约 2.59 GB）并安装 3 个 APK，已发 INIT 广播
- 初始化完成后验收（2026-09-15 10:38）：SSH / `:8000` / ADB 均通；IP 仍为 `192.168.88.216`；家目录已清空；userdata 占用约 12G / 剩余 66G；AidLite `2.3.2.251`、OpenCV `4.13.0` 仍在；MediaPipe 未装

### 误跑 apt upgrade 2026-09-15

- 10:41 `sudo apt upgrade`：`libkmod2` 升到 `29-1ubuntu1.1`，`kmod` 停在 `29-1ubuntu1`；`systemd` / `udev` / `util-linux` 等约 31 个包 `iU`（已解包未配置）
- 根因：`mod-blacklist 1.0-r0` 占用 `/etc/modprobe.d/blacklist.conf`，新 `kmod` 无法覆盖
- 修复：`dpkg -i --force-overwrite kmod=29-1ubuntu1.1` + `apt-get --fix-broken install`（`--force-confold`），**没有**继续全量 upgrade
- 修完：`kmod`/`libkmod2` 均为 `ii 29-1ubuntu1.1`；`dpkg --audit` 干净；AidLite `2.3.2.251`、OpenCV `4.13.0`、C920 `/dev/video2` 仍可用
- 源里仍有约 265 个可升级包，保持不升级

### 皮影跟影 2026-09-15（已换掉）

- 未装 PyPI `mediapipe`（板上 DNS 到不了 pypi.org）。改用官方示例模型 + AidLite TFLite GPU
- 全身皮影需要整个人入画，C920 工位视野不够，已不再作为宣传主线

### 工位回血 2026-09-15

- 上半身 BlazePose：`pose_landmark_upper_body.tflite`（31 点）+ 检测阈值 0.42
- 局内循环：在位/离开、静坐计时、满 20 分钟提醒、4 动作回血清零、`save.json` 按天续算
- 摄像头叠像素火柴人；任务：展翅 / 老鹰 / 挥手 / 滑雪 / 弹琴 / 举手跳 / 转头 / 点头
- 底栏实测：Pose 检出约 70–110 ms（TFLite GPU），未检出约 33 ms；NPU YOLOv5s QNN236 脉冲约 9–20 ms
- `:8090` HTTP 200，`/status` 回 JSON

### USB 摄像头 2026-09-15

- 型号：Logitech HD Pro Webcam C920，`lsusb` `046d:082d`，Bus 003 Port 4，驱动 `uvcvideo`，480M
- 采集：`/dev/video2`；`/dev/video3` 是 UVC metadata，OpenCV 打不开
- 板载仍在：`video0`=`cam-req-mgr`，`video1`=`cam_sync`，`video32/33`=`msm_vidc_decoder`
- OpenCV `CAP_V4L2` + MJPG + 1280×720：`probe.py` 循环约 30.46 fps（平均 32.82 ms）
- 同分辨率 YUYV 驱动只报 10 fps（USB2 带宽），教程必须写先设 MJPG
- 已抓到实景帧（人像，不入库）；板上路径 `~/rhinopi-lab/captures/`

### 登录验收

- [x] ping
- [x] SSH
- [x] `:8000` HTTP 200
- [ ] Web 桌面完整登录截图（待拍）
- [ ] HDMI 本机桌面（未测）

### 体检数字（2026-09-14，640 输入，warmup 5 + loops 20）

在板子 `~/rhinopi-lab/examples/02_compute_bench` 跑 `python3 bench.py`：

| 后端 | 平均 | 最小 | 最大 | 说明 |
| --- | --- | --- | --- | --- |
| numpy | 15.841 ms | 11.556 | 23.960 | 640×640 float 运算 |
| OpenCV 预处理 | 3.446 ms | 0.760 | 18.291 | 1280×720 → 640 resize + blur |
| AidLite QNN236 DSP | 4.772 ms | 4.634 | 4.967 | YOLOv5s W8A8；set_input + invoke + get_output，无后处理；约 210 inf/s |

AidLite 日志确认设备已授权。NPU 标准差 0.107 ms，很稳。

### 失败与备注

- 板子不是干净镜像，家目录占用很大。教程命令不要假设 `~` 是空的。
- 未执行刷机，也未执行 `apt upgrade`。
- Cursor 内置浏览器访问局域网 `:8000` 未成功渲染；本机 `Invoke-WebRequest` 为 200。截图请用电脑浏览器拍。
