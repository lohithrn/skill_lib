# Reference — what a baked avatar contains

One directory per avatar, `avatars/<name>/`. Everything the runtime needs is here; everything here was
produced by `jobs/bake.md`.

## Layout

| Path | What it is |
|---|---|
| `atlas.mp4` | every baked frame, `libx264 -crf 16 -preset slow`, **25 fps** — the runtime's pixel source |
| `frames/*.png` | the full dump. Indices **beyond** the mp4's length are selector / enhancer / ladder appendices that exist **only** as PNGs. |
| `atlas.json` | the cursor map (schema below) |
| `meta.json` | `fps`, `frame_size [w,h]`, `face_box [x1,y1,x2,y2]`, `n_frames`, `engine`, `drivers` |
| `blink/` | `eye{0,1}_{half,closed}.png` (RGBA, alpha = feathered mask) + `blinks.json` + `strip.png` |
| `brows/` | `brow{0,1}.png` (RGBA) + `brows.json` + `strip.png` |
| `validation.json` | the acceptance-gate report — the proof this avatar behaves |
| `sheet.png` | contact sheet of the 8 chosen visemes, for your eyes only |
| `enhance_compare.png` | before/after face restoration, for your eyes only |
| `lp_renders/` | cached driver renders from step 1 — expensive to recreate, safe to delete |

## `atlas.json`

```json
{
  "fps": 25,
  "frame_size": [762, 508],
  "n_frames": 0,
  "visemes":          {"sil": 2730, "aa": 2733, "…": 0},
  "viseme_neighbors": {"aa": [2731, 2732, 2733, 2734, 2735]},
  "blend_ladder":     {"aa": [[0.35, 0], [0.7, 0]]},
  "phonemeMap": {}, "digraphMap": {}, "viseme_list": []
}
```

- `visemes` maps each of the **8** visemes — `sil pp ff aa e i o u` — to the index of the **whole**
  frame that best shows that shape. Not a crop, not a region: a whole frame.
- `viseme_neighbors` is the micro-motion preload set. It exists so the decode pass fetches those
  frames too; the runtime never renders a frame it did not preload.
- `blend_ladder` gives each viseme its pre-baked **0.35** and **0.7** openness poses. Missing rungs
  mean the runtime falls back to a live crossfade, which is exactly the blur the ladder removed.
- `phonemeMap` / `digraphMap` are the grapheme→viseme tables the runtime uses to read text.
- Indices are the contract between steps. Step 1 wipes stale PNGs precisely because a shifted index
  space makes every entry in this file point at the wrong picture, with no error anywhere.

`meta.json`'s `face_box` is measured from frame `00000.png` with a **10 px** pad. Both the mouth band
and the static (forehead/eyes) band used by the gates are derived from it, so a wrong box silently
changes every gate threshold's meaning — see `references/validation.md`.

## The caveat that bites every fresh checkout

`frames/` is deliberately untracked — it is around **1 GB** — but the enhanced and ladder frames that
`atlas.json` references live **only** there, as PNGs beyond the mp4's range. So a fresh checkout of a
committed avatar directory cannot serve it: the mp4 decode yields the original frames and the PNG
fallback finds nothing.

There is no repair path. Re-run the bake. In principle steps 2–6 suffice when `atlas.mp4` and
`meta.json` survive, but step 2 needs the **full** frame dump, so in practice you re-run
`bake_avatar.py` from step 1 (`jobs/bake.md`).

Do not "fix" this by committing the frames, the atlas video, the model weights or any other binary.
The size is the reason the split exists; `references/weights.md` covers what must never be committed.
