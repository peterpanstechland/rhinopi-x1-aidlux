# USB 摄像头探测

插到犀牛派 **Type-A** 口，在 Ubuntu 侧运行：

```bash
cd ~/rhinopi-lab/examples/usb_camera
python3 probe.py
```

脚本会区分板载节点和 USB 采集节点，用 MJPG 抓一帧并测循环帧率。静图默认写到 `~/rhinopi-lab/captures/usb_preview.jpg`。

本机已验证：联调板 `192.168.88.216`，Logitech C920，`/dev/video2`，1280×720 MJPG 约 30 fps。
