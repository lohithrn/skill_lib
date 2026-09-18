# Job — run, redeploy and smoke-test a server

One process per avatar, one port each. The process binds its atlas at import time, so there is no
per-request avatar switch and no reason to make one.

## Launch

```bash
pkill -9 -f cpu_server.py
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES ATLAS_DIR=avatars/<name> PORT=8820 \
  .venv-cpu/bin/python cpu_server.py
```

| Variable | Meaning |
|---|---|
| `ATLAS_DIR` | the avatar directory — absolute, or relative to the project root. Defaults to `frame_pack_atlas`. |
| `PORT` | the HTTP port. Server default is **8800**; the house convention below overrides it. |
| `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` | **required on macOS** — without it the server aborts mid-job on its first fork. No-op on Linux. |
| `SWAY` | `1` re-enables head sway and nods. Default off — see `references/replay-contract.md`. |
| `PIPER_MODEL` | the Linux/ARM voice, when the local `say` backend is absent. |

**Port convention: 8820 = the newest avatar, 8821 = the original `frame_pack_atlas`.** Keep it. The
convention is what makes "is the new bake live?" answerable without reading a process list.

Health check after a redeploy — expect `200`:

```bash
python3 -c 'import urllib.request as u; print(u.urlopen("http://127.0.0.1:8820/", timeout=5).status)'
```

The startup line prints the atlas size, fps and viseme count. Read it: it is the fastest way to catch
`ATLAS_DIR` pointing at the wrong avatar.

## HTTP contract

| Endpoint | Method | Contract |
|---|---|---|
| `/` | GET | the player page |
| `/api/stream` | POST | `{"text": "...", "voice": <opt>, "rate": 175}` → `{"job": "<12-hex-id>"}`. Empty text is a **400**. |
| `/api/job/<id>` | GET | `{"status", "done", "segments", "stream", "duration"}`. Unknown id is a **404**. |
| `/poster.png` | GET | the current avatar's `sil` frame, as the idle poster |
| `/out_cpu/<path>` | GET | the HLS playlist and segments |

`status` walks `queued → synthesizing → streaming → done`, or `error` with an `error` string.
`stream` is the playlist path, `/out_cpu/stream_<id>/stream.m3u8`.

Two properties of this design that are easy to undo by accident:

- **The render runs in an isolated child process**, not a thread. A native fault in numpy, Pillow or
  the ffmpeg pipe then cannot take the HTTP server down with it. The child reports progress by
  writing `status.json` into its own output directory, and `/api/job/<id>` reads that file — which is
  why job state survives a worker crash and why the endpoint never blocks on the render.
- **One long-lived ffmpeg HLS muxer per job**, fed raw frames as they are produced. One muxer pass
  means continuous timestamps, so audio is gapless while segments are written live: playback starts
  quickly and can sustain arbitrarily long speech. Restarting the muxer mid-utterance reintroduces the
  audio seam this design removed.

Encode settings (change them and you undo the enhance step): `libx264 -preset fast -tune zerolatency
-crf 16 -pix_fmt yuv420p`, GOP = fps, audio `aac -b:a 128k` at **48000 Hz** stereo, HLS
`-hls_time 1.0 -hls_list_size 0 -hls_flags independent_segments -hls_segment_type mpegts
-hls_playlist_type vod`.

## Smoke test

`assets/smoke_stream.py` is the whole test: POST one utterance, poll the job to completion, print the
playlist path, exit non-zero on error or timeout. Stdlib only, `localhost` only.

```bash
python3 assets/smoke_stream.py --port 8820 --text "The big moon rose over the calm lake."
```

Pass criteria: `status: done`, `done: true`, `segments >= 1`, and a `stream` path that exists on
disk. A job that reaches `done` with **0** segments means ffmpeg accepted no frames — check the
`error` field and the server's stderr, not the player.

## The player

- **The stage must stay native size.** Native 3:2, `width: min(762px, 100%)`, `object-fit: contain`.
  A covering square stage once upscaled the **762×508** video **1.9×** — see the non-negotiables in
  SKILL.md. Any CSS change here needs a visual check at 100% zoom.
- The page polls `/api/job/<id>` every **150 ms** until the playlist has a segment, then hands the
  URL to the HLS player. Do not add a second retry loop around a failed segment fetch: re-polling a
  segment hammers the server toward port exhaustion. A single delayed reload of the source is the
  fix that shipped.
- After editing the player, hard-refresh the browser. A cached page is the most common "my change
  did nothing".

## Known operational noise

- Background server tasks killed during a redeploy emit "aborted" notifications afterwards. Expected.
  Confirm the new pair answers **200** and move on.
- No TTS backend on the box is a hard error at synthesis time, not at startup: the job goes to
  `error` with `No TTS backend found`. The runtime itself only needs a wav — see the refusals in
  SKILL.md.
- A server that starts but shows a frozen mouth is almost always a runtime-timeline problem, not a
  server problem: go to `references/replay-contract.md`.
