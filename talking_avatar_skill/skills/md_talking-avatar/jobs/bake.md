# Job — bake an avatar from a portrait

One command, any number of images. Run it from the project root.

```bash
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES python3 bake_avatar.py portraits/<image>.png
# -> avatars/<image>/    ~2-4 min per portrait on an Apple-silicon Mac
```

`bake_avatar.py` is an orchestrator only: it runs **7 steps, each in its own venv**, in order, and
fails the whole bake if any step exits non-zero. Nothing about a step's behavior lives in the
orchestrator — read the step's own script when you need to change one.

Before you start, confirm the weights and venvs exist (`references/weights.md`). A missing
checkpoint fails at step 1 or 3 with a torch load error, which is a confusing way to learn that a
file was never downloaded.

## Input requirements

- A **frontal portrait**. Step 1 needs a face MediaPipe can landmark; step 1 aborts with
  `no face found` otherwise.
- The image basename becomes the avatar name: `portraits/<image>.png` → `avatars/<image>/`.
- Step 1 **deletes stale PNGs** in the target `frames/` first. A leftover dump from a previous bake
  would shift the index space and silently corrupt every viseme reference in `atlas.json`.

## The 7 steps

| # | Step | Script | Venv | What it owns |
|---|---|---|---|---|
| 1 | bake | `bake_viseme_atlas_lp.py` | `.venv-liveportrait` | LivePortrait drives the portrait with expressive clips at `animation_region="lip"` — whole-face articulation. Dumps every frame, encodes `atlas.mp4`, writes `meta.json`. |
| 2 | select | `select_atlas_visemes.py` | `.venv-mediapipe` | MediaPipe measures the lips in **every** frame and picks the best frame per viseme: `sil pp ff aa e i o u`. |
| 3 | enhance | `enhance_atlas.py` | `.venv-lipsync` | GFPGAN restores **only the selected frames**, onto one shared base. |
| 4 | ladder | `bake_blend_ladder.py` | `.venv-lipsync` | Pre-renders each viseme's **0.35** and **0.7** openness poses and restores them too. |
| 5 | blinks | `bake_blinks.py` | `.venv-mediapipe` | Half/closed eyelid RGBA crops warped from the `sil` frame. |
| 6 | brows | `bake_brows.py` | `.venv-mediapipe` | Raised-brow RGBA crops, same overlay technique. |
| 7 | validate | `validate_avatar.py` | `.venv-cpu` | **Acceptance gates** through the real runtime. Non-zero exit fails the bake. |

A contact sheet (`sheet.png`) is rendered between steps 6 and 7 so the 8 chosen visemes can be
eyeballed — that is a convenience, not a gate.

### Step 1 — why LivePortrait is the default engine

Wav2Lip paints a **96×96** mouth box: the lips move while the jaw, chin, cheeks and nasolabial folds
stay frozen, which reads as "only the lips spark" on a dead face. LivePortrait is an
implicit-keypoint portrait animator — opening the mouth drops the jaw and stretches the cheeks
coherently, at much higher native resolution, giving genuinely rounded `o`/`u` and about **2×**
Wav2Lip's mouth distinctness. Head pose and eyes stay pixel-frozen, so every frame stays aligned
with the source outside the mouth.

Facts that are easy to break here:

- `animation_region="lip"` restricts motion to mouth+jaw. Widening it unfreezes the eyes and
  forehead and destroys the pinning the runtime and the `confinement` gate depend on.
- **Stitching must stay on.** Without paste-back LivePortrait emits bare **512×512** face crops
  instead of full source-size frames, which corrupts the atlas geometry *silently* — every frame
  still exists, at the wrong size.
- `.pkl` motion templates **fail** with `animation_region="lip"` (no `c_d_eyes_lst` data). Video
  drivers only.
- Five driving clips are used (`d0`, `d3`, `d6`, `d9`, `d13`). Measured coverage on the reference
  portrait: **2378** frames, mouth opening **0–65 px**, every shape class present — closed **1160**,
  big-open **83**, spread **223**, rounded **35**. Rounded shapes are the scarcest, which is why
  `o`/`u` are historically the weak visemes.
- Renders are cached in `lp_renders/` because each driver costs minutes on MPS. Re-running the step
  reuses them; delete the cache to force a re-render.
- Output fps is **25**.

Legacy engine: `BAKE_ENGINE=wav2lip` switches step 1 to `bake_viseme_atlas.py` in `.venv-lipsync`
(mouth-box-only motion). Same output contract, worse mouths. Keep it working — it is the fallback
when a portrait breaks the keypoint animator.

### Step 2 — selection is a measurement, not a taste call

The selector measures open / width / roundness / redness per frame on the face-box region (landmarks
need the crop) but the runtime always emits the **whole** frame. It prints per-viseme
cost/open/width/round; `o` and `u` are the shapes to check first.

On the legacy engine the frame pool mixes GAN and non-GAN checkpoint output. A non-GAN frame wins
only if its shape cost is better by the **×0.95** margin; it is then LAB colour-corrected from the
shape-nearest GAN donor (non-GAN output goes blue/purple around the mouth) and **re-validated** on
both shape and redness before it is accepted. A colour-corrected pick that fails re-validation is
dropped, not kept.

### Step 3 — one base, or the whole face shimmers

GFPGAN output varies slightly frame to frame in the eyes and skin. Restoring each viseme
independently makes shape switches shimmer. So the step builds **one** enhanced base from the `sil`
frame and pastes only each viseme's enhanced **mouth region** onto it through a feathered elliptical
mask: every output frame is pixel-identical outside the mouth. Enhanced frames are appended as new
indices and `atlas.json` is updated.

**Re-run steps 5 and 6 after step 3** so the eyelid and brow crops are cut from the enhanced base.
The orchestrator already does this in order; a manual re-run of step 3 alone leaves stale overlays.

### Step 4 — the ladder exists because crossfades blur lips

Blending `sil` and a viseme at runtime is a ghost of two sharp images. Instead each in-between pose
is rendered offline (blend, then GFPGAN-restore the blend so the ghost becomes a plausible sharp
half-open mouth) at levels **0.35** and **0.7**, and stored as `blend_ladder` in `atlas.json`. The
runtime then does zero pixel math — it snaps to the nearest rung.

### Steps 5 and 6 — overlays are legal because the upper face never moves

Both engines leave the upper face untouched across every atlas frame, so one crop pair per eye and
one per brow, baked once from the `sil` frame, composites onto **any** frame. Crops are RGBA where
alpha is the feathered blend mask, so the runtime needs numpy only — no OpenCV in the serving venv.
The closed lid is synthesized by stretching the upper-lid skin band down to the lower lash line
(eyes are visually forgiving; mouths are not). Each script self-validates — eye-aspect-ratio drop for
blinks, eye-brow gap increase for brows — and writes a `strip.png` preview.

## Re-running one step

Every step is standalone and idempotent against an existing avatar directory:

```bash
<venv>/bin/python <script>.py --out avatars/<name>
.venv-cpu/bin/python validate_avatar.py avatars/<name>     # takes the dir as its only arg
```

Order still matters: 2 needs 1's full frame dump, 3 and 4 need 2's picks, 5 and 6 need 3's base, and
7 needs everything. Re-running step 1 invalidates all of them.

## When you are done

The bake prints `n_frames` and the viseme count, plus a ready-to-paste server command. Then:

1. Read `validation.json` — every gate must say `pass` (`references/validation.md`).
2. Look at `sheet.png` once, for the shapes a number cannot describe.
3. Serve it: `jobs/serve.md`.

What each artifact is and what `atlas.json` guarantees: `references/artifacts.md`.
