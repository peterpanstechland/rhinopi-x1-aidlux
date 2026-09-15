#!/usr/bin/env python3
import json
import urllib.request

import paramiko

print("==== status")
try:
    with urllib.request.urlopen("http://192.168.88.216:8090/status", timeout=5) as r:
        d = json.loads(r.read().decode())
    print(json.dumps(d, ensure_ascii=False))
except Exception as exc:
    print("status err", exc)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.88.216", username="aidlux", password="aidlux", timeout=15, allow_agent=False, look_for_keys=False)
for cmd in (
    "grep -aE 'Traceback|Error|error:' /tmp/puppet.log | head -n 20",
    "grep -ao 'frame [0-9]* fps=.*' /tmp/puppet.log | tail -n 8",
):
    print("====", cmd)
    _, o, _ = c.exec_command(cmd, timeout=15)
    print(o.read().decode(errors="replace"))
c.close()
