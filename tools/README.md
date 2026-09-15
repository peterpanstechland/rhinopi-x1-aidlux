# 本机联调工具

只在写教程的电脑上用，用来 SSH 到联调板。默认地址 `192.168.88.216`，账号密码是官方默认值 `aidlux` / `aidlux`。

```bash
python tools/probe_board.py
python tools/probe_camera.py
python tools/deploy_and_run.py
python tools/deploy_and_run.py --skip-npu
```

需要本机已装 `paramiko`。
