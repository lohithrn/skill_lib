#!/usr/bin/env python3
"""Smoke-test one talking-avatar server: speak once, poll the job, report.

Stdlib only, localhost only. This lives in assets/ (not scripts/) precisely
because it talks to a socket: everything under scripts/ in this collection is
offline by contract.

    python3 assets/smoke_stream.py --port 8820 --text "..."

Pass criteria, all of them:
    status == "done", done is true, segments >= 1, and a stream path was given.

Exit 0 = pass. Exit 1 = the server reported an error, produced no segments, or
did not finish inside --timeout. Exit 2 = the server was unreachable.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

DEFAULT_TEXT = "The big moon rose over the calm lake. We see it clearly tonight."


def call(url: str, payload: dict | None = None, timeout: float = 10.0) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8820, help="server port (8820 = newest avatar)")
    ap.add_argument("--text", default=DEFAULT_TEXT, help="what the avatar should say")
    ap.add_argument("--timeout", type=float, default=120.0, help="seconds to wait for done")
    ap.add_argument("--interval", type=float, default=0.5, help="poll interval in seconds")
    args = ap.parse_args()

    base = f"http://127.0.0.1:{args.port}"
    try:
        job = call(f"{base}/api/stream", {"text": args.text})["job"]
    except (urllib.error.URLError, OSError) as exc:
        print(f"UNREACHABLE  {base}: {exc}")
        return 2
    print(f"job {job}")

    deadline = time.time() + args.timeout
    last = ""
    status: dict = {}
    while time.time() < deadline:
        try:
            status = call(f"{base}/api/job/{job}")
        except (urllib.error.URLError, OSError) as exc:
            print(f"UNREACHABLE  mid-job: {exc}")
            return 2
        state = str(status.get("status", "?"))
        if state != last:
            print(f"  {state}  segments={status.get('segments', 0)}")
            last = state
        if state == "error":
            print(f"FAIL  {status.get('error', 'no error field')}")
            return 1
        if status.get("done"):
            break
        time.sleep(args.interval)
    else:
        print(f"FAIL  not done after {args.timeout:.0f}s (last status {last!r})")
        return 1

    segments = int(status.get("segments", 0))
    stream = status.get("stream") or ""
    if segments < 1 or not stream:
        # done with zero segments means ffmpeg accepted no frames: read the
        # server's stderr, not the player.
        print(f"FAIL  done but segments={segments} stream={stream!r}")
        return 1
    print(f"PASS  segments={segments} duration={status.get('duration')} stream={stream}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
