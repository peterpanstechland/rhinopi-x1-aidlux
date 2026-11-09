#!/usr/bin/env python3
from __future__ import annotations

import shlex
import sys

import paramiko

from deploy_game import run_remote, upload_game


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        "192.168.88.216",
        username="aidlux",
        password="aidlux",
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    try:
        upload_game(client)
        # The bracketed pattern keeps the stop command from matching its own shell.
        stop = "pkill -TERM -f '[0]6_shadow_puppet/game.py'"
        rc = run_remote(client, stop, timeout=10)
        if rc not in (0, 1):
            return rc
        argv = [
            "python3", "/home/aidlux/rhinopi-lab/examples/06_shadow_puppet/game.py",
            "--port", "8090", *sys.argv[1:],
        ]
        cmd = shlex.join(argv)
        ready = "sit interval " if "--no-web" in argv else "HTTP listening on "
        launch = f"""
            : > /tmp/puppet.log || exit 1
            setsid nohup {cmd} >> /tmp/puppet.log 2>&1 < /dev/null &
            pid=$!
            for i in $(seq 1 60); do
                if ! kill -0 "$pid" 2>/dev/null; then cat /tmp/puppet.log; exit 1; fi
                if grep -q '^{ready}' /tmp/puppet.log; then echo "started $pid"; exit 0; fi
                sleep 1
            done
            tail -n 20 /tmp/puppet.log
            echo "Game startup was not confirmed within 60 seconds." >&2
            exit 1
        """
        return run_remote(client, launch, timeout=75)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
