# MediaPipe / AidLite Pose

联调板访问不了 PyPI，也没有现成的 `mediapipe` wheel。这里用融合系统自带的 **AidLite TFLite BlazePose**（官方「人体姿势检测和跟踪」同一套模型）。

```bash
cd ~/rhinopi-lab/examples/04_mediapipe
python3 pose_preview.py
```

电脑浏览器打开 `http://<板子IP>:8091/`。默认 USB `/dev/video2`，镜像预览。

模型路径：`/opt/aidlux/app/aid-examples/pose_detect_track/models/`。
