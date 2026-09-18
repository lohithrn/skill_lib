---
name: md_talking-avatar
description: Build, run, debug and improve a GPU-bake / CPU-replay talking avatar — a frontal portrait photo becomes a photoreal talking head streamed over HLS from hardware with no GPU. Use when the user mentions avatars, lip sync, visemes, a viseme atlas, baking an image, Wav2Lip, LivePortrait, GFPGAN, blinks/brows, mouth shiver or blur, HLS avatar streaming, or asks to make a portrait talk.
when_to_use: The user wants a portrait to speak, or is debugging a baked avatar's mouth shapes, shiver, blur, timing, ports or stream.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Talking Avatar — bake on the GPU, replay on the CPU

A router. Portrait photo in, photoreal talking head out, streamed as HLS from a box with **no GPU**.
The procedures live in `jobs/`, the contracts and the numbers in `references/`. Read the gate, pick
one row of the route table, read that file, and do not read the others.

The companion skill `md_director` generates a fresh clip per request from a prompt. This skill generates
**nothing** at request time. It pays for the pixels once, offline, and the runtime only reorders
frames it already has. That trade is the architecture — every rule below exists to keep it true.

## The gate — read this first

1. **The bake/replay split is not an optimization, it is the deployment contract.** The runtime target
   is **2 vCPU, 8 GB RAM, no GPU, ARM64, ≤2 GB image**. Any change that puts neural inference,
   `torch`, or per-request pixel synthesis into the request path makes the service undeployable — not
   slower. The runtime venv must **never** gain `torch`.
2. **No weights, no bake.** The pipeline depends on checkpoints and models that are not in any repo
   and must not be committed. If they are absent, say which one and stop — see
   `references/weights.md`. Do not substitute a different checkpoint to make a step "work".
3. **Measure, do not eyeball.** Every bake ends in acceptance gates that load the avatar through the
   *real* runtime and exit non-zero on failure. After any change, re-run them: `references/validation.md`.
4. **Ask before retuning the movement budget.** `movements_per_sec = 4.0` and the perceptual hold
   times are user-tuned through six values. They are not defaults.

## Route

| The user wants | Read | Writes files? |
|---|---|---|
| a new avatar from a portrait image | `jobs/bake.md` | yes — a new avatar directory |
| to run, redeploy or smoke-test a server | `jobs/serve.md` | no — starts a process |
| to debug timing, flutter, blur, shiver, or a dead mouth | `references/replay-contract.md` then `references/validation.md` | no |
| to know what a baked avatar contains, or why a fresh checkout cannot serve one | `references/artifacts.md` | no |
| to know which model weights are needed and where they come from | `references/weights.md` | no |
| to prove a change did not regress the avatar | `references/validation.md` | writes `validation.json` |

## The split, in one table

| | Offline — "bake" | Runtime — "replay" |
|---|---|---|
| Hardware | Apple-silicon Mac, MPS/GPU | any CPU, no GPU, no `torch` |
| Cost | **~2–4 min** per portrait | faster than realtime; target **≥60 fps** render |
| Neural work | LivePortrait (or Wav2Lip), GFPGAN, MediaPipe | none |
| Output | an avatar directory: `atlas.mp4` + `atlas.json` + overlays | frames piped to ffmpeg → HLS |
| Per request | nothing | text → TTS wav → envelope + word alignment → whole frames |

The runtime decodes only the **~35** atlas frames it can actually show (**~100 MB** RAM) instead of
all **~500** full frames (**~1.6 GB**). Everything it shows was rendered offline and restored offline.

## Non-negotiables — each one is a bug that already happened

1. **Never composite a mouth crop onto a face.** Replay whole frames. Crop-pasting produced visible
   seams and lighting mismatch and was rejected as "ugly"; the bake engines inpaint the lower face
   *in place*, so the whole frame is already correct.
2. **Never blend frames at runtime.** Snap to a pre-baked, GFPGAN-restored ladder rung. A live
   numpy crossfade ghosts two lip edges together, so the lips go blurry *exactly while talking* —
   the one moment the viewer is looking at them.
3. **Never let the player upscale.** The stage is native 3:2, capped at the source's **762 px**
   width (**762×508**). A square `object-fit: cover` stage once upscaled **1.9×** and cropped the
   face: the worst blur bug in the project's history, and none of the bake quality survived it.
4. **Pauses must freeze the mouth.** VAD gates openness to **0** in silence. A mouth that keeps
   moving through a pause reads as a puppet no matter how sharp the frames are.
5. **Shapes come from word-level alignment, not from global peak order.** Assigning shapes to
   loudness peaks in sequence matched only **~20%** of words, and drifted permanently after the
   first mismatch. Word windows took it to **100%** (13/13 on the reference sentence).
6. **`movements_per_sec = 4.0` is user-tuned** (it went 5 → 7 → 6.5 → 6 → 5.5 → 4). Ask before
   changing it. Raising it makes the face chatter; lowering it makes the face mumble.
7. **Every bake and every server launch on macOS needs `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`.**
   Without it the Flask server aborts mid-job the moment it forks a worker, ffmpeg or TTS. It is a
   no-op on Linux, so set it unconditionally.
8. **Encode with `-preset fast -crf 16`** (plus `-tune zerolatency` for HLS). ffmpeg's defaults smear
   the restored lip detail, which throws away the entire enhance step.
9. **One server process per avatar, one port each.** The runtime binds one atlas directory at import
   time; there is no per-request avatar switch. Two avatars means two processes.

## Numbers not to touch without asking

| Knob | Value | What breaks if you move it |
|---|---|---|
| `movements_per_sec` | **4.0** | chatter above, mumble below (rule 6) |
| ladder rungs | **0.35**, **0.7** | fewer rungs → visible openness stair-stepping |
| pose hysteresis margin | **0.16** in the runtime | below it, adjacent rungs alternate A/B/A/B and read as blur |
| minimum pose hold | **2** frames, floor **0.08 s** | a 1-frame pose flash reads as shimmer around the mouth |
| `pp` forced openness | **≥0.7** while speaking | m/b/p are quiet but the most recognizable shape; unforced, they vanish |
| openness attack / release | **0.55** / **0.35** | symmetric smoothing makes speech look soft-edged |
| encode | `-crf 16` | higher CRF smears lips (rule 8) |

Full derivation and the rest of the constants: `references/replay-contract.md`.

## Index

| File | The question it answers |
|---|---|
| `jobs/bake.md` | How do I turn a portrait into an avatar, and what does each of the 7 steps own? |
| `jobs/serve.md` | How do I run, redeploy and smoke-test a server, and what is the HTTP contract? |
| `references/replay-contract.md` | What exactly does the runtime do per request, with which numbers? |
| `references/artifacts.md` | What is inside an avatar directory, and what does `atlas.json` promise? |
| `references/weights.md` | Which weights and venvs are required, where do they come from, when do I refuse? |
| `references/validation.md` | Which gates must pass, at what thresholds, and how do I measure by hand? |

`jobs/serve.md` also uses `assets/smoke_stream.py` — a stdlib-only client that POSTs one utterance
and polls the job to completion.

## What this does NOT do

- **It does not run without the baked weights and models.** The bake needs a face-restoration
  checkpoint, a face-landmarker model and a bake engine's weights; the runtime needs the offline
  ASR model for word alignment. None of them live in a repo and none may be committed. If one is
  missing, name it and stop rather than degrading silently — `references/weights.md` lists what each
  absence costs.
- **It does not serve an avatar from a fresh checkout.** The avatar's `frames/` directory is
  deliberately untracked (**~1 GB**) but the atlas references enhanced and ladder frames that exist
  only there, beyond the mp4's range. A fresh checkout must re-run the bake; there is no repair path.
- **It does not do neural inference at request time, ever** — not "not yet". No `torch` in the
  runtime venv, no mouth synthesis per utterance, no GPU on the serving box. See the gate.
- **It does not promise realtime on CPU for anything but replay.** The realtime claim covers frame
  *reordering* (gate threshold **≥1.5×** playback fps, hand-check target **≥60 fps**). Baking is
  offline and takes minutes per portrait on a GPU; it is not a request-time operation on any hardware.
- **It does not composite, crop, blend or upscale.** Rules 1–3 are refusals, not preferences. If a
  request needs a mouth pasted onto another face, that is a different pipeline.
- **It does not ship a TTS engine.** The runtime only needs a wav. The local `say` path is
  macOS-only; a Linux/ARM deployment must supply its own CPU voice that returns a wav.
- **It does not switch avatars inside a running process,** and it does not manage the process for
  you: killing the old server before redeploying is part of `jobs/serve.md`.
