# 登录与环境

先进得去、网通了，再确认 Python / OpenCV / AidLite，最后才装体验依赖。

## 目标

- 用 HDMI、Web 桌面或 SSH / ADB 登录 Ubuntu
- 确认融合系统版本和预装组件
- 跑通环境检查脚本
- USB / CSI 先做设备探测（没插相机也可以）

## 相关资料

- [软件架构概述](https://developer.aidlux.com/software/architecture)
- [浏览器登录](https://rhinopi.docs.aidlux.com/rhino-x1-ubuntu/getting-started/quick-start/quickstart_web)
- [USB 摄像头](https://rhinopi.docs.aidlux.com/rhino-x1-aidlux/basic-dev/vision/usb_camera)
- [AidLite / AidCV](https://developer.aidlux.com/software/aidlite)

## 登录三条路

默认用户名和密码都是 `aidlux`。Web 桌面地址：

```text
http://<板子IP>:8000/login
```

推荐顺序：

1. **HDMI 本机桌面**：插显示器和键鼠，适合第一次确认系统活着。
2. **Web 桌面**：电脑和板子同一局域网，浏览器打开上面的地址。渲染界面用 AidCV，和 OpenCV API 对齐。
3. **SSH / ADB**：拷文件、跑脚本。

```bash
ssh aidlux@<板子IP>
```

或电脑用 Type-C 连接后：

```bat
adb devices
adb shell
```

### 联调板（已验证）

- IP：`192.168.88.216`（`eth0`）
- SSH 22、Web `8000` 均开放
- `ssh aidlux@192.168.88.216` 默认密码可登录
- <http://192.168.88.216:8000/login> 返回 HTTP 200

板子上还有 `br-lan`（`192.168.1.1/24`），是板载 LAN 网段，不要和上行 `eth0` 搞混。

## 本机已验证的系统快照

2026-09-14 在联调板上采集：

- 内核：`Linux 5.15.178-android13-... aarch64`（Android 13 内核 + Ubuntu 用户态，即融合系统）
- 用户态：Ubuntu 22.04.2 LTS
- CPU：6 核，最高约 3.19 GHz
- 内存：约 14 GiB 可见
- 用户分区：约 79G
- Python 3.10.12
- OpenCV 4.13.0，numpy 1.26.4
- AidLite Python / C：`2.3.2.251`（20260410）
- 已装：`aidlite-sdk`、`aidlite-qnn236`、`aidlite-onnx`、`aidlite-tflite`、`aidcv-sdk`、`aidstream-gst`、`aid-mms`、`aidgen-qnn236`
- `aid-pkg`、`mms` 可用
- MediaPipe：**未安装**
- 刷完未插相机时：`/dev/video0`、`video1`、`video32`、`video33` 仍在（板载节点，不是 USB）
- 2026-09-15 已插 USB：Logitech HD Pro Webcam C920（`046d:082d`），采集节点 `/dev/video2`

## 在板子上跑环境检查

把本仓库拷到板子（任选一种）：

```bash
# 在你的电脑上，仓库根目录
scp -r examples aidlux@192.168.88.216:~/rhinopi-lab/
```

然后 SSH 进去：

```bash
cd ~/rhinopi-lab/examples/01_env_check
python3 check_env.py
```

脚本会打印系统、Python 模块、AidLite、`/dev/video*`、`lsusb`。完整输出可贴进 [实测记录](experience-log.md)。

## 刷完还要装什么

分两层，不要一上来 `pip install` 一堆包。

### 系统层（先确认预装）

融合系统通常已带 Python3、OpenCV、AidLite、MMS。先跑 `check_env.py`，缺什么再补。

NPU 后端版本必须和模型广场详情卡上的 QNN 一致。联调板当前是 `aidlite-qnn236`。安装或对齐时用：

```bash
sudo aid-pkg update
# 版本号以 aid-pkg 列表和模型卡片为准，不要照抄过期文档里的 qnn216
sudo aid-pkg install aidlite-sdk
sudo aid-pkg install aidlite-qnn236
```

验证：

```bash
python3 -c "import aidlite; print(aidlite.get_py_library_version())"
```

### 体验层（下一阶段才装）

- MediaPipe、可视化依赖：给 Pose 和工位回血用
- 模型：走 [模型广场](04-modelfarm.md) / `mms`，不要自己随便下一份 Ultralytics 权重当主路径

当前 **不要** 在联调板上执行全量 `apt upgrade` / `apt dist-upgrade`。融合镜像的 Ubuntu 源是活的，会把 `kmod`、`systemd`、`python3.10` 等和厂商包拧到一半。社区同款记录：[apt upgrade 修复](https://forum.aidlux.com/t/topic/74814)。

缺软件用点装，例如 `sudo apt install <包名>`，或走 `aid-pkg`。

### 已经跑过 upgrade 怎么办（联调板已修）

典型报错：

```text
kmod : Depends: libkmod2 (= 29-1ubuntu1) but 29-1ubuntu1.1 is installed
E: Sub-process /usr/bin/dpkg returned an error code (1)
```

这是 `libkmod2` 先升到 `29-1ubuntu1.1`，`kmod` 被厂商包 `mod-blacklist` 占着 `/etc/modprobe.d/blacklist.conf` 升不上去。此时 `systemd` / `udev` 往往停在「已解包未配置」，**先不要重启**。

只修这一对，不要再全量 upgrade：

```bash
# 板子 Ubuntu
sudo cp -a /etc/modprobe.d/blacklist.conf /etc/modprobe.d/blacklist.conf.bak
cd /tmp
apt-get download kmod=29-1ubuntu1.1
sudo dpkg -i --force-overwrite /tmp/kmod_29-1ubuntu1.1_arm64.deb
sudo DEBIAN_FRONTEND=noninteractive apt-get --fix-broken install -y \
  -o Dpkg::Options::="--force-confold"
sudo dpkg --audit    # 应无输出
```

`dpkg -i` 当时可能报 `libkmod2 is not configured yet`，接着跑 `--fix-broken` 即可。`--force-confold` 会留下厂商的 `blacklist.conf`。

2026-09-15 联调板按上面修完：`kmod` / `libkmod2` 均为 `29-1ubuntu1.1`，AidLite / OpenCV / C920 仍可用。源里还有两百多个可升级包，**不要继续 `apt upgrade`。**

## 摄像头验收

USB 接到板子 **Type-A** 口（不要插 Type-C 调试口），然后：

```bash
lsusb
ls -l /dev/video*
v4l2-ctl --list-devices
```

对照官方 [USB 摄像头](https://rhinopi.docs.aidlux.com/rhino-x1-aidlux/basic-dev/vision/usb_camera) 的识别方式：多出来的 `video` 节点才是 UVC，板载节点一直都在。

### 联调板（已验证，Logitech C920）

| 节点 | sysfs 名 | 用途 |
| --- | --- | --- |
| `/dev/video0` | `cam-req-mgr` | 高通相机请求管理，不是 USB |
| `/dev/video1` | `cam_sync` | 相机同步，不是 USB |
| `/dev/video2` | `HD Pro Webcam C920` | **USB 采集**，OpenCV 走这里 |
| `/dev/video3` | `HD Pro Webcam C920` | UVC metadata，`cv2.VideoCapture` 打不开 |
| `/dev/video32` `/dev/video33` | `msm_vidc_decoder` | 硬解节点，不是摄像头 |

`lsusb` 为 `046d:082d Logitech, Inc. HD Pro Webcam C920`，挂在 USB 2.0（480M）`uvcvideo`。官方示例相机是 `05a3:9230`，同样落在 `video2` / `video3`。

抓帧不要写 `VideoCapture(0)`。在板子上：

```bash
cd ~/rhinopi-lab/examples/usb_camera
python3 probe.py
```

C920 在 1280×720 用 **YUYV 只有 10 fps**（USB2 带宽），必须先设 **MJPG** 才能到 30 fps。本机实测循环约 **30.5 fps**，单帧平均 32.8 ms。静图写到 `~/rhinopi-lab/captures/`。

官方 Web 桌面「手部姿势识别」也可点一遍对照。CSI 见 [MIPI CSI](https://rhinopi.docs.aidlux.com/rhino-x1-aidlux/hardware-use/mipi_csi)，主线先 USB。

## 本步验收

- SSH 或 Web 桌面能进
- `check_env.py` 里 AidLite、OpenCV 为 OK
- 记下 IP、内核、AidLite 版本
- 插了 USB 相机后，`probe.py` 能从采集节点抓到帧

## 常见失败

| 现象 | 先查什么 |
| --- | --- |
| ping 不通 | 网线是否在 WAN/`eth0`；本机是否同一网段 |
| `:8000` 打不开 | AidLux 是否初始化完；防火墙；改用 SSH |
| SSH 拒绝 | 确认 `aid-ssh` 服务；密码是否改过 |
| `import aidlite` 失败 | `dpkg -l \| grep aidlite`，按卡片版本重装插件 |
| `kmod` / `libkmod2` 版本对不上 | 刚跑过 `apt upgrade`；按上文只修 kmod，不要再全量升级 |
| 没有 `/dev/video*` | 未插 USB 时仍可能有板载节点；USB 相机再看 `lsusb` |
| `VideoCapture(0)` 黑屏 / 打不开 | 0 是板载节点；UVC 采集一般是 `video2`，先 `v4l2-ctl --list-devices` |
| 720p 只有十几帧 | 默认常是 YUYV；OpenCV 先 `CAP_PROP_FOURCC=MJPG` |

## 拍照点

见 [拍照清单](photo-checklist.md) 第 2 组。
