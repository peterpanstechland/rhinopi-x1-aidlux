#!/usr/bin/env python3
import paramiko

CMDS = [
    r"find /opt/aidlux /usr/local/share -maxdepth 6 -iname '*hand*' 2>/dev/null | head -n 40",
    r"find /opt/aidlux /usr/local/share -maxdepth 6 -iname '*palm*' 2>/dev/null | head -n 40",
    r"find / -maxdepth 7 -iname '*hand_landmark*' 2>/dev/null | head -n 20",
    r"ls -la /opt/aidlux/app/aid-examples/ 2>/dev/null",
    r"ls -la /opt/aidlux/app/aid-examples/pose_detect_track/models/ 2>/dev/null",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.88.216", username="aidlux", password="aidlux", timeout=20, allow_agent=False, look_for_keys=False)
for cmd in CMDS:
    print("====", cmd)
    _, o, e = c.exec_command(cmd, timeout=90)
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace").strip()
    if err:
        print("ERR", err[:400])
c.close()
