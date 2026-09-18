# Reference — venvs, weights, and when to refuse

Four virtual environments, five model artifacts, one rule: **nothing here is committed, and nothing
here is substituted.** If a weight is missing, name it and stop.

## The four venvs

| Venv | Used by | Key deps |
|---|---|---|
| `.venv-liveportrait` | step 1, the default bake engine (MPS) | torch, the portrait-animator repo and its weights |
| `.venv-lipsync` | the legacy bake engine, enhance, ladder (MPS) | torch, opencv, gfpgan, librosa |
| `.venv-mediapipe` | select, blinks, brows | mediapipe, opencv |
| `.venv-cpu` | the runtime, the server, the acceptance gates | numpy, PIL, flask, the offline ASR package |

**`.venv-cpu` must never gain `torch`.** That venv is what ships to a **2 vCPU / 8 GB / no GPU /
ARM64 / ≤2 GB image** target; a torch dependency alone blows the image budget, before any inference
happens. This is the split's load-bearing constraint, not a packaging preference.

The venvs are separate because their dependency sets genuinely conflict — which is why a step that
"needs one small import from another venv" is a subprocess boundary, not a merge. Step 1 already does
this: it measures the face box by shelling out to the MediaPipe venv, because MediaPipe is not
installed alongside the animator.

## The model artifacts

All live under `models/`, all untracked, all re-downloadable from upstream. None may be committed.

| Artifact | What needs it | Where it comes from |
|---|---|---|
| `wav2lip_gan.pth`, `wav2lip.pth` | the legacy bake engine (`BAKE_ENGINE=wav2lip`) | the Wav2Lip project's published checkpoints |
| `GFPGANv1.4.pth` | enhance (step 3) and ladder (step 4) | the GFPGAN releases page, `TencentARC/GFPGAN`, v1.3.0 tag |
| `face_landmarker.task` | select, blinks, brows, and the step-1 face box | the MediaPipe face-landmarker task bundle |
| `vosk-model-small-en-us-0.15/` | word-level alignment at runtime, and the `words` gate | the upstream Vosk model list, `alphacephei.com/vosk/models` |
| `gfpgan/weights/` | face-restoration auxiliaries | fetched automatically on the first restoration run |

The portrait animator additionally needs its own repo checkout and weights inside
`.venv-liveportrait`'s tree, plus the driving clips that ship with it (`d0`, `d3`, `d6`, `d9`, `d13`).

## What to refuse, and what each absence costs

| Missing | Symptom if you push on | Refuse with |
|---|---|---|
| animator repo or weights | step 1 exits `LivePortrait failed on driver …` | "the bake engine's weights are absent" — do not fall back to the legacy engine silently; say you are doing it and why |
| `GFPGANv1.4.pth` | step 3 or 4 dies on a torch load; without them the mouth is soft at **96×96** upscale quality and the ladder rungs are ghosts | "no face-restoration checkpoint — a bake without step 3 fails the sharpness expectation and the ladder is pointless" |
| `face_landmarker.task` | step 1 aborts `no face found`; steps 2/5/6 cannot measure anything | "no landmarker model — selection, blinks and brows are all measurements, and none can run" |
| ASR model or package | the runtime **silently** falls back to global peak order (**~20%** word accuracy) and the `words` gate is **skipped**, not failed | "word alignment is unavailable, so this avatar cannot be validated for word correspondence" — never report a bake as passing on a skipped gate |
| any TTS voice | jobs fail at synthesis with `No TTS backend found` | "the box has no CPU voice; the runtime needs a wav and does not make one" |

The ASR row is the dangerous one: it is the only absence that produces a working-looking avatar with
the accuracy of the design the word alignment replaced. Check for the skip line in the gate output.

## Never commit, never generate

- No checkpoints, no `.pth`, no model bundles, no `atlas.mp4`, no frame dumps, no wavs, no HLS
  segments. Binaries are what the bake/replay split exists to keep out of the repo.
- Do not mint credentials of any kind to reach a model host, and do not add an auth step to this
  pipeline: every artifact above is a public upstream download, and the servers here bind
  `localhost` with no auth surface at all. Adding one is a design change, not a fix.

## The one install fix worth remembering

`gfpgan`'s dependency `basicsr` breaks against newer torchvision. Patch the installed
`basicsr/data/degradations.py` in place:

```
from torchvision.transforms.functional_tensor import rgb_to_grayscale
->
from torchvision.transforms.functional import rgb_to_grayscale
```

The module moved; nothing else about the dependency is wrong. Pinning an older torchvision instead
drags the whole MPS bake stack backwards.
