# Reference — the replay contract

What the CPU runtime does per request, with every constant it uses. No neural inference, no `torch`,
no GPU: numpy, Pillow and ffmpeg only. If you are debugging a mouth that mumbles, chatters, blurs,
shivers or freezes, the cause is on this page.

## The per-request pipeline

| # | Stage | Detail |
|---|---|---|
| 1 | TTS | text → wav, **48000 Hz** stereo, rate **175**. Any CPU voice will do; the runtime reads the wav, nothing else. |
| 2 | Envelope | per-video-frame RMS loudness, decoded mono at **16 kHz**, hop = `16000 / fps`, smoothed with a **3-frame** box. Smoothing keeps syllable peaks and kills jitter. |
| 3 | VAD | speech mask from the envelope: threshold **0.12 ×** the **97th** percentile, gaps of **≤4** frames closed, runs shorter than **2** frames dropped. |
| 4 | Word alignment | offline ASR gives per-word timestamps; they are matched to the **known** text with difflib. |
| 5 | Shape timeline | each word's own syllable shapes are placed inside that word's window, thinned by measured impact. |
| 6 | Openness | per-frame from instantaneous loudness, normalized per speech segment. |
| 7 | Pose choice | nearest pre-baked ladder rung, with hysteresis and minimum holds. |
| 8 | Overlays | pose → blink → brow → translate, in that order. |
| 9 | Mux | whole frames piped to ffmpeg → HLS. |

## Why word alignment, and what it bought

The text is always **known**, so alignment is a constrained problem, not recognition. The offline ASR
pass yields `{word, start, end}`; difflib matches its words to the transcript, matched words inherit
exact timings, and unmatched words are interpolated linearly between their nearest matched anchors
and clamped to the audio length. Every transcript word therefore gets a window.

The alternative — assign shapes to loudness peaks in global order — matched **~20%** of words and
drifted permanently after the first mismatch. Word windows took per-word shape accuracy to **100%**
(13/13 on the reference sentence). The peak-order path still exists as a fallback for when the
aligner or its model is unavailable; it is a degradation, not an option.

## The movement budget

- `movements_per_sec = 4.0`, user-tuned through **5 → 7 → 6.5 → 6 → 5.5 → 4**. Ask before changing it.
- Minimum anchor spacing `min_dist = max(2, round(fps / movements_per_sec))`.
- Per word: `slots = min(len(beats), word_frames // min_dist + 1)`, then thinned by measured impact —
  drastic shapes survive, subtle ones are dropped.
- Anchors prefer loudness peaks inside speech (local maxima, the real syllable nuclei, with the louder
  of two contenders kept when they fall inside `min_dist`), and fill evenly when peaks are scarce.

**Impact is measured per avatar, not assumed.** At startup the runtime computes the mean absolute RGB
distance between every pair of actual baked viseme frames and normalizes to 0–1. A hand-written shape
table assumes ideal visemes; a real bake may come out with a barely-rounded `o`. Measuring the real
pixels means "drastic" means drastic *on this face*.

## Openness

| Rule | Value | Why |
|---|---|---|
| Silence | openness **0**, shape `sil` | the avatar pauses exactly when the voice pauses |
| Per-segment reference | **90th** percentile of the segment | soft speech still articulates |
| Amplitude lift | `w ** 0.65` | a smoothstep suppressed mid loudness into weak, non-drastic movement |
| Attack / release | **0.55** / **0.35** | open fast, close a touch slower — movements cannot outrun the voice |
| Below **0.04** | emit `sil` outright | avoids a permanently ajar mouth |
| Between word windows, VAD still on | shape `sil`, openness **× 0.35** | word boundaries have to articulate |
| `pp` while speaking | openness forced **≥0.7** | m/b/p are acoustically quiet and visually the most recognizable shape; unforced they never register |

## Pose stability — three guards, all necessary

1. **Nearest rung, never a blend.** Levels are `[(0.0, sil), (0.35, …), (0.7, …), (1.0, viseme)]`; the
   runtime picks the nearest and shows that pre-baked frame. A live crossfade ghosts two lip edges
   together and reads as blurry lips while talking.
2. **Same-shape hysteresis, margin 0.16.** Openness wobbles every frame, so nearest-rung snapping
   alternates between two adjacent rungs — A/B/A/B flicker that reads as blur. Stay on the current
   rung unless the target is clearly closer to a new one. (An older note put this margin at 0.10;
   the shipped runtime uses 0.16. Read the code before quoting either.)
3. **No pose may flash for one frame.** A 1-frame pose flip shimmers around the mouth and nose even
   when every frame is sharp, so a pose that has been shown fewer than **2** frames holds.

### Perceptual minimum holds

Anchor spacing alone makes hold time random: `pp` might get 1–2 invisible frames while a filler vowel
lingers. Each run is grown into neighbouring runs of **lower** priority — never below the neighbour's
own minimum, never past a word edge.

| Viseme | Minimum hold | Priority |
|---|---|---|
| `pp` | **0.20 s** | **3.0** |
| `aa`, `o`, `u` | **0.16 s** | **2.0** |
| `e`, `i` | **0.12 s** | **1.5** |
| `ff` | **0.16 s** | **1.0** |
| anything else | **0.08 s** | 0 |

Donor floor: `sil` and no-word territory keep **2** frames; a shape keeps its own minimum.

## Static-region pinning — the shiver killer

GFPGAN restores each baked pose independently, so nose and cheek texture differ microscopically
between poses. At 5–7 pose switches per second those differences read as **the whole face
shivering**. At load the runtime measures where real articulation happens (max smoothed diff versus
`sil` across all loaded frames), feathers that mask, and composites every frame onto `sil` — outside
the mouth zone the face becomes pixel-identical across all poses.

Do not disable this to "get more motion". The `confinement` and `no_shiver` gates exist to prove it is
still on (`references/validation.md`).

## The alive-face layer

Applied per frame, in order: **pose → blink → brow → translate**.

| Layer | Numbers | State |
|---|---|---|
| Blinks | pattern `half / closed / closed / half` — **4** frames, **160 ms** at 25 fps — every **2–5 s**, first one between **0.7 s** and **1.8 s** so even a short utterance gets one | on |
| Brow raises | on peaks above the **90th** percentile of speech loudness, at least **2.2 s** apart; ramp **3** frames up, hold **0.3 s**, **5** frames down, starting **2** frames early | on |
| Nods | on peaks above the **75th** percentile, at least **1 s** apart, raised-cosine over **0.5 × fps** frames, amplitude **1.6 px** | **off** |
| Head micro-sway | two incommensurate sines, **±1.5 px** over **6.7 s** and **±1.1 px** over **8.3 s**, integer-pixel edge-pad crop (no resample blur), running even during pauses | **off** |

Sway and nods are **disabled by default** and gated behind `SWAY=1`: integer-pixel hops of the whole
frame were reported as the face shivering, which is worse than a still head. The code stays because
the seam is deliberate — re-enable it for experiments, not for a shipped avatar, and never in the same
change as a mouth fix.

## Memory and speed

The runtime decodes only the frames it can show — best-per-viseme, their neighbours, and every ladder
rung — in **one** ffmpeg pass with a `select` filter, so the full video is never materialized:
**~35** frames and **~100 MB** instead of **~500** frames and **~1.6 GB**. Anything the mp4 does not
yield is filled from the PNG sequence, which is how the selector's appended frames (indices beyond the
original video's range) are reachable at all — see `references/artifacts.md`.

Render speed must stay **≥60 fps** in the serving venv, and the gate demands **≥1.5×** playback fps.
Both are cheap to lose: any per-frame OpenCV or torch import in this path fails the deployment
contract in SKILL.md, not just the benchmark.
