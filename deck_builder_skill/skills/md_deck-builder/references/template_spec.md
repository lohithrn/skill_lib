# Template Spec — what to extract before you build

**Every value on this page is a PLACEHOLDER describing a reference template.** Extract the real ones
from your own template (`assets/template.pptx`, or wherever you keep it) and use those. Do not brand
from memory, and do not ship a deck built on the placeholders — it will be off-brand and the reason
will not be visible in the render.

Introspect once, write the values down, build from your notes. If in doubt, unpack the template and
look: `python3 -c "import zipfile; zipfile.ZipFile('template.pptx').extractall('unpacked')"`.

## Colour tokens

Role names are the contract; the hexes are defaults you overwrite. `scripts/ooxml_helpers.py` holds
the same tokens as module constants — change them there once and every pattern follows.

| Token | Role | Placeholder | Where the real value lives |
|---|---|---|---|
| `ACCENT` | Primary brand accent. Subtitles, accents, badges, chevron. | `2B6CB0` | the content layout's subtitle placeholder run properties |
| `ACCENT_ALT` | The shade template chrome/subtitle actually uses. Prefer `ACCENT` for new fills. | `3182CE` | same placeholder, second shade |
| `DARK` | Dark bands, callout blocks, card headers. | `1B2233` | the title/divider slide backgrounds |
| `INK` | Body text on light. | `1A1E28` | content body runs |
| `SLATE` | Secondary/muted body text. | `5A6172` | content body runs |
| `LIGHT` | Content-slide background tint (or plain white). | `F4F5F7` | content layout background |
| `BORDER` | Card outlines. | `E4E6EB` | pick to sit ~1 step off `LIGHT` |
| `RED` | Risk / "can't claim yet" / negative comparison. | `841018` | semantic, not brand — keep unless your brand defines one |
| `GREEN` | Positive / "with" / deliverable. | `2E7D5B` | semantic |
| `MAGENTA` | Third accent for A/B/C differentiation. | `C92C8F` | semantic |
| `AMBER` | Status pill for "new". | `E8A33D` | semantic |

Never prefix hex with `#` in pptxgenjs or OOXML fills. In OOXML use `<a:srgbClr val="2B6CB0"/>` —
a `#` there is silently dropped and the shape renders black.

> **Trust the placeholder, not the theme.** A template's *theme* accent is usually an Office
> default left untouched, while the real brand accent is written explicitly on the content
> subtitle. Read the subtitle's own run colour and use that; the theme accent will be a near-miss
> that reads as "close but wrong" on every slide.

## Fonts

- **Check the theme font's availability before you rely on it.** A template themed on Aptos, for
  example, has **no metric-compatible substitute** and is missing on older Office — every QA render
  reflows.
- **Safe fonts** (render true in QA and ship with Office): body **Calibri**, headers with
  personality **Cambria** (serif). Use these unless your brand font is installed everywhere.
- Big stat numbers: Cambria bold reads as premium. Body copy: Calibri.

## Title & subtitle (content slides)

These are the native placeholders on the blank content slide. **Keep them** — they inherit correct
formatting:

- **Title placeholder:** position (0.36", 0.36"), size 12.5" × 0.35", **24pt bold, ALL-CAPS**,
  inherits near-black. One line maximum.
- **Subtitle placeholder:** position (0.36", 0.72"), size 12.48" × 0.31", **18pt**, `ACCENT_ALT`.
  Optional; one line maximum.

When restyling a content slide, preserve the title `<p:sp>` verbatim (swap only its text) and reuse
the subtitle placeholder for the one-line deck-specific subtitle.

## Footer chrome — INHERITED, never drawn

The footer is part of the content layout and appears automatically on any slide using that layout:

- wordmark, lower-left
- accent chevron block, lower-right
- the confidentiality/legal line
- page-number field (native `<a:fld>` — auto-increments; do NOT hardcode page numbers as text, that
  caused drift bugs in the past)

**Do not draw a footer.** Duplicating the blank content slide gives you the inherited footer for free.

## The other four slides

- **Title slide.** Dark background, logo top-left, hero image right, white bold title, accent italic
  tagline, date. **Edit text only.**
- **Section dividers (two variants).** Dark, "Section Title" in the accent colour, optional caption
  on the second variant. **Edit text only.** Use only for multi-section decks (~**8**+ slides).
- **Closing / capstone.** Dark "THANK YOU", office list, contact line, logo. **Edit text only, or
  leave as-is.**

## Layout indices

The reference template numbers these layouts **12** (blank content), **13** (title), **14**
(closing), **15**/**16** (dividers). Yours will differ. Read
`ppt/slides/_rels/slideN.xml.rels` for each slide, map the five roles to your own numbers, and pass
them to `scripts/qa_gate.py` with `--content-layout`, `--title-layout`, `--closing-layout` and
`--divider-layouts`. A gate run against the wrong indices checks nothing and passes.
