# 拍照清单

拍完把文件放到 `docs/images/`，文件名按下面来，方便挂进正文。

## 第 1 组：开箱与刷机

新板或重装时拍。联调板已在跑，这组可以后补。

- `01-board-front.jpg`：板子正面，能看清接口
- `01-board-ports.jpg`：Type-C、DC、网口、USB-A、HDMI
- `01-cables.jpg`：电源和 Type-C 线序
- `01-qfil-config.jpg`：QFIL FireHose 配置
- `01-qfil-9008.jpg`：9008 端口
- `01-qfil-success.jpg`：Download successful
- `01-aidlux-init.jpg`：AidLux 初始化进度

## 第 2 组：登录与环境

- `02-web-login.jpg`：`http://<ip>:8000/login`
- `02-web-desktop.jpg`：登录后的 Web 桌面
- `02-ssh.jpg`：SSH 登录后的 `uname -a` / `hostname`
- `02-env-check.jpg`：`python3 check_env.py` 末尾摘要
- `02-lsusb.jpg`：插上 USB 相机后的 `lsusb`（联调板应为 C920 `046d:082d`）
- `02-video-nodes.jpg`：`ls -l /dev/video*` 或 `v4l2-ctl --list-devices`
- `02-usb-preview.jpg`：`probe.py` 抓到的静图（不要把别人脸拍进公开稿）

## 第 3 组：算力体检

- `03-bench-cpu.jpg`：CPU / OpenCV 输出
- `03-bench-npu.jpg`：NPU 循环输出（有模型时）
- `03-temp.jpg`：体检前后温度（可选）

## 第 4 组：模型广场

- `04-farm-filter.jpg`：芯片选 QCS8550、精度 INT8
- `04-farm-card.jpg`：某张模型性能卡
- `04-farm-download.jpg`：网页「模型 & 代码」
- `04-mms-list.jpg`：板上 `mms list yolo`
- `04-official-run.jpg`：官方 `run_test.py` 结果

## 第 5 组：推理与游戏

- `05-mediapipe-pose.jpg`：Pose 叠点
- `05-yolo-detect.jpg`：YOLO 检测框
- `05-desk-break.jpg`：工位回血（火柴人 + 积分 + 底栏 benchmark）
- `05-csi-connector.jpg`：CSI 座子与排线
- `05-csi-preview.jpg`：CSI 预览

## 拍的时候注意

- 屏幕类直接截图比手机拍更清楚
- 终端把字体调大，不要截一整桌
- 不要把改过的密码、Token、模型广场账号拍进图里
