# Reference — the acceptance gates and how to measure by hand

The bake's last step is not a report, it is a **gate**. It loads the avatar through the *real* runtime
— the exact code path the server uses — speaks a phonetically rich sentence, writes
`validation.json`, and **exits non-zero** so a bad bake never silently ships.

```bash
.venv-cpu/bin/python validate_avatar.py avatars/<name>
```

Test sentence, verbatim, because the numbers below were tuned on it:

> The big moon rose over the calm lake. We see it clearly tonight.

Two things are isolated during the run so the mouth is measured alone: blinks are stubbed out and the
motion tracks are zeroed. Blinks and brows are validated by their own bake steps, and leaving them on
would put motion into the "nothing outside the mouth may change" band.

## The measurement bands

Both come from `meta.json`'s `face_box`, so a wrong box changes what every threshold means:

- **mouth band** — from **62%** down the face height to the chin plus **14 px**, inset **18%** from each side.
- **static band** — forehead and eyes **only**: the top **45%** of the face, from **10 px** above it.

The static band stops at 45% on purpose. On a whole-face engine the nose base, cheeks and chin
*legitimately* articulate with the jaw; that is natural motion, not shiver. A static band that
included them would fail every good bake.

## The gates

| Gate | Threshold | What a failure means |
|---|---|---|
| `artifacts` | all **8** visemes (`sil pp ff aa e i o u`) present, ladder non-empty, blink crops present | a step was skipped or wrote nothing; brows are reported but not required |
| `distinctness` | `aa` diff vs `sil` in the mouth band **≥2.0**, and no vowel below `max(1.2, 0.30 × aa)` | the selector could not find real shapes — check the printed per-viseme cost and `sheet.png`; `o`/`u` fail first |
| `confinement` | max forehead/eyes diff vs `sil`, across all poses, **≤0.45** | static-region pinning is off or the mask is wrong; the face will shiver |
| `no_flashes` | minimum pose hold **≥2** frames **and** switch rate within **3–9 /sec** | below 3/sec the face mumbles, above 9/sec it chatters, and a 1-frame hold shimmers |
| `no_shiver` | max frame-to-frame change in the static band, while speaking, **≤0.6** | motion is leaking outside the mouth during playback even though the held poses agreed |
| `excursion` | peak mouth diff **≥80%** of the full `aa` excursion | the runtime never opens the mouth all the way — usually the openness curve, not the bake |
| `realtime` | rendered fps **≥1.5 ×** playback fps | something expensive entered the per-frame path |
| `words` | **≥90%** of test words show a matching shape | shapes are landing outside their word windows |

`validation.json` records every gate with a `pass` flag and its measured detail, plus a top-level
`passed`. **A skipped gate is not a passed gate.** `words` is skipped when the aligner or its model is
absent (`references/weights.md`) and the run prints `SKIP words …`; a bake reported as good on a
skipped `words` gate is a bake with **~20%** word accuracy.

## Measure these by hand after any change

The gates are the floor, not the ceiling. Do this too — do not eyeball only:

| Property | How | Expectation |
|---|---|---|
| Word→shape correspondence | align the words, render, check the shapes shown inside each word window against that word's syllable beats | every word matched — 13/13 on the reference sentence |
| Pose flutter | count content switches between consecutive frames | each pose holds **≥3** frames (the gate's floor is 2; 3 is the target) |
| Bake shape quality | read the select step's per-viseme cost / open / width / round, then look at `sheet.png` | `o` and `u` are the historically weak shapes |
| Sharpness | Laplacian variance on the mouth box — the enhance and ladder steps print it | restored frames clearly above the raw pick |
| Speed | render a sentence in the serving venv | **≥60 fps** |
| Blinks and brows | the bake steps self-validate (eye-aspect-ratio drop, eye-brow gap increase) and write `strip.png` | look at both strips once |

## Reading a failure

| Symptom | Start at |
|---|---|
| mouth blurs while talking | ladder rungs missing (`references/artifacts.md`) or a live crossfade path |
| whole face shivers | `confinement` / `no_shiver` — static-region pinning in `references/replay-contract.md` |
| mouth moves in pauses | the VAD threshold, same file |
| shapes lag or lead the words | the aligner, same file — and check whether it fell back to peak order |
| everything looks soft in the browser only | the player stage upscaled; see the non-negotiables in SKILL.md |
| a gate regressed after a bake-step edit | re-run the whole bake. Steps share an index space; a partial re-run can pass a gate on stale frames (`jobs/bake.md`). |
