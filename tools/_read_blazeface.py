#!/usr/bin/env python3
from pathlib import Path

import paramiko

OUT = Path(__file__).resolve().parents[1] / ".tmp_hand"
OUT.mkdir(exist_ok=True)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.88.216", username="aidlux", password="aidlux", timeout=20, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()
base = "/opt/aidlux/app/aid-examples/hand_track"
sftp.get(f"{base}/blazeface.py", str(OUT / "blazeface.py"))
st = sftp.stat(f"{base}/models/anchors.npy")
print("palm anchors size", st.st_size)
sftp.close()
c.close()
print("saved blazeface.py")
