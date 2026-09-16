# 工位回血

久坐 + 坐姿监测，配一组上半身伸展挑战。像素舞台上有一个 Minecraft 风格的数字人，跟着你的上半身动。

```bash
python3 game.py                       # 25 分钟提醒；坐姿不对额外扣血
python3 game.py --demo                # 45 秒就催，录像用
python3 game.py --interval-min 15 --round-acts 6
python3 render_probe.py --out /tmp/ui  # 不用人也能渲染每一屏，核对排版
```

`http://<板子IP>:8090/`  状态：`/status`

## 两种画面

| 阶段 | 画面 |
| --- | --- |
| 久坐监测 / 提醒 / 离开 | 摄像头实时画面 + 像素 overlay，右侧坐姿评分 |
| 挑战回合 / 总结 | 上下分屏：上半是像素舞台和数字人，下半是实时小窗 + 倒计时 + 坐姿 |

## 流程

满 25 分钟（或 HP 被坐姿扣光）弹提醒，展翅或举手开始。**每组 2 分钟**，每个动作一屏，过了 challenge 才算过关，自动跳下一屏，最后出总结。

| 动作 | challenge |
| --- | --- |
| 展翅 | 双臂撑满 3 秒 |
| 老鹰 | 鸟翅扇动 8 次，云往后飞就是升空 |
| 挥手 | 月台送行，左右挥手送走 10 个人 |
| 滑雪 | 俯视下坡，左右倒身碰 6 面旗、躲松树 |
| 弹琴 | 手部 landmark，按中 10 个键 |
| 跳跃 | 椅上颠身跳过 5 个仙人掌 |
| 转头 | 左右各转 3 次 |
| 点头 | 点头 6 次 |

## 模型

| 用途 | 模型 |
| --- | --- |
| 上半身姿态 | `pose_detect_track/models/pose_landmark_upper_body.tflite`（TFLite GPU） |
| 手部 21 点 | `hand_track/models/palm_detection.tflite` + `hand_landmark.tflite`（只在弹琴那一屏加载） |
| NPU 底栏 | `cutoff_yolov5s_...qnn236.ctx.bin`（QNN236 DSP 脉冲） |

坐姿评分看四项：低头前伸、塌坐、歪肩、离屏太近。回合结束后会按当时的坐姿重新标定基线。
