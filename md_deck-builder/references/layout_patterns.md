# Layout Patterns — content slides

These are the high-value, reusable patterns for the **body region of a duplicated blank content
slide**. The title/subtitle placeholders stay native; these shapes go **below** them (content region
roughly y = 1.5" to 6.4", full width 0.55"–12.8").

All coordinates in inches on the 13.33 × 7.5 canvas. In raw OOXML, EMU = inches × **914400**.
Colour names below are the tokens from `template_spec.md` — swap the values, keep the roles.

## Authoring method

Two ways to add body shapes to a duplicated content slide:

1. **pptxgenjs** onto a *separate* generated deck — not preferred here, it can't inherit the template
   footer.
2. **Direct OOXML** appended into the duplicated `slideN.xml`'s `<p:spTree>` (preferred — keeps native
   footer). Build shape XML strings and insert before `</p:spTree>`. Register any icon images in the
   slide's `.rels` and `[Content_Types].xml`.

A Python helper (`scripts/ooxml_helpers.py`) provides `rrect()`, `rect()`, `ellipse()`, `txt()`,
`pic()`, `icon_chip()` that emit these strings. Reuse it rather than hand-writing XML.

## Shared building blocks

- **Card:** rounded rectangle, fill `FFFFFF`, 1px border `BORDER`, soft drop shadow (blur ~90k EMU,
  dist ~30k, dir 5400000, alpha ~26%).
- **Icon chip:** filled circle (`ACCENT` or a semantic color) + white icon PNG inset ~**46%** of the
  circle diameter.
- **Dark band:** rounded rectangle fill `DARK`, no border, used for "why us / key point" anchors.
  White/`E8EBF2` text, accent label.

---

## Pattern 1 — Icon-signal rows (left) + stat cards (right)

Good for a "situation / why now" slide. Three rows on the left, two stat cards on the right.

- Row: icon chip (0.6" dia) at x≈0.55; bold header 15pt at x≈1.3; description 12.5pt slate below.
  Rows spaced ~1.35" apart starting y≈2.1.
- Stat card: card at x≈8.1, w≈4.65, h≈1.9; big number 36pt Cambria bold in `ACCENT` or `DARK`; label
  13pt slate below. Two stacked.

## Pattern 2 — A/B/C labeled option cards (three across)

Three cards, each with a colored square tag (A/B/C) top-left, an icon chip top-right, a bold title, a
description, and a pinned italic accent note at the bottom in the card's accent color. Card w≈3.95,
gap≈0.28, x0≈0.55, top≈1.75, h≈4.75. Differentiate the three with `ACCENT` / `DARK` / `MAGENTA`.

## Pattern 3 — Staged flow with arrows (Today → Risk → Fix)

Three cards left-to-right with an accent "→" (30pt bold) between them. Each card: icon chip + bold
stage header + description. Card w≈3.75, gap≈0.55. Below, a dark "why us" band (full width, fill
`DARK`) with an icon chip, an accent label, and a two-run paragraph (white lead-in + softer
follow-up). Use semantic colors: `DARK` (today), `RED` (risk), `GREEN` (fix).

## Pattern 4 — Two-column comparison (Without / With, Before / After)

Two cards side by side (w≈6.0 each, gap≈0.8, top≈2.85, h≈3.55). Each card has a colored header strip
(rounded rect, h≈0.7): left header `6B7080` (neutral/negative) with a "ban" icon + "WITHOUT"; right
header `ACCENT` with a "check" icon + "WITH". Body is a bulleted list (1.35–1.5 line spacing, ~9pt
paraSpaceAfter), slate on the left, ink on the right. Optionally a full-width context band above
(light accent tint) with an icon + a two/three-run sentence highlighting the key stat.

## Pattern 5 — Branded table (objections / capabilities / status)

The signature table. Full width from x≈0.55.

- **Header row:** three (or N) solid rectangles, each a semantic color — e.g. `DARK` (dimension),
  `GREEN` (positive), `RED` (caveat). White bold 12.5pt header text, letter-spaced.
- **Body rows:** alternating fills `FFFFFF` / `EDEFF3`, 0.5px border `BORDER`, row height ~1.1",
  cells vertically centered (`anchor="m"`), **single line — no wrapping**. First column bold italic
  dark; middle column ink; caveat column red.
- **Status pills** (when showing state): small rounded rects with semantic fill — `GREEN`
  (done/ongoing), `AMBER` (new), `MAGENTA` (mixed) — white text inside.

## Pattern 6 — Stat callout row + dark anchor band

Four stat cards across (w≈2.95, gap≈0.2, top≈1.65, h≈2.55): icon chip, big number (34pt Cambria bold
in a per-card accent color), small label. Below, a full-width dark band (`DARK`) with an icon chip, an
accent ALL-CAPS label, and a 14.5pt light paragraph — use it to land the honest/anchoring point (e.g.
"THE HONEST KT PROBLEM").

## Pattern 7 — Numbered "The Ask" grid (2×2)

Four cards in a 2×2 grid (w≈6.0, gap≈0.25, h≈1.55). Each: a large faint number (44pt Cambria bold, a
light tint of `ACCENT`) at left, an accent icon chip, a bold header, a description. Below, a
full-width dark band with a centered bold italic punchline (19pt).

---

## Composition guidance

- Pick **3–5** different patterns across a content deck; never repeat one on every slide (design
  principle #4, #10 in `design_principles.md`).
- Anchor argument-style decks with a dark band (patterns 1/3/6/7) on the most important slides.
- Keep text within card bounds — reduce font or split before overflowing (see
  `iteration_checklist.md`).
- Icons: render an icon font/set to white PNG at ≥**256px**; embed with the `image/png;base64,`
  prefix if using pptxgenjs, or as slide-rel media if authoring OOXML directly. Always white on
  colored chips.
- Semantic color meaning is consistent: accent = brand/positive-accent, dark = neutral/structure,
  green = good/with, red = risk/caveat, magenta = third differentiator.
