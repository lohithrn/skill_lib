# The `<product>` UI theme

The palette and rules every new frontend in the fleet copies. Extracted from one product's
`frontend/app/globals.css`; where that file and this one disagree, read the file.

## Palette (CSS variables on `:root`)

```css
:root {
  --ink: #17201c;         /* text, and the primary button / brand-mark background */
  --muted: #69736d;       /* secondary text, subtitles */
  --line: #dfe4df;        /* every border */
  --paper: #fbfcf9;       /* strips and inset areas */
  --panel: #ffffff;       /* cards */
  --lime: #c7f06b;        /* accent — used AS TEXT on --ink, not as a fill */
  --lime-dark: #31540b;
  --blue: #2877e5;
  --blue-soft: #e9f1ff;
  --amber: #f0ad37;
  --amber-soft: #fff7e7;
  --red-soft: #fff0ec;
  --shadow: 0 18px 50px rgba(36, 49, 42, 0.08);
}
```

Page background is **`#f1f4ef`** — slightly darker than `--paper`, so panels lift off it without needing
a heavy shadow.

## Type

```css
font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

Heavy weights and tight tracking are the signature: `font-weight: 800`/`900` with
`letter-spacing: -0.02em` to `-0.08em` on brand and headings. Buttons at `font-weight: 750`.
`button, input { font: inherit; }` so nothing falls back to a UA font.

## Structural pieces

| Piece | Recipe |
|---|---|
| Topbar | `height: 76px`, `padding: 0 28px`, flex space-between, `border-bottom: 1px solid var(--line)`, `background: rgba(251,252,249,.94)`, `backdrop-filter: blur(16px)`, `position: sticky; top: 0; z-index: 20` |
| Brand mark | 38×38, `border-radius: 11px`, `display: grid; place-items: center`, `--ink` background with `--lime` glyph, `font-weight: 900`, `letter-spacing: -0.08em` |
| Status pill | `inline-flex`, `gap: 8px`, `padding: 8px 12px`, `border-radius: 999px`, `1px solid var(--line)`, white, `font-size: 12px`, `font-weight: 700` |
| Pulse dot | 8×8 circle, `#67b21e`, `box-shadow: 0 0 0 4px #e5f5d5` — the halo is the effect |
| Primary button | `--ink` background, white text, `min-width: 190px`, `padding: 15px 20px`, `border-radius: 10px`, `box-shadow: 0 8px 24px rgba(23,32,28,.18)`, `border: 0` |
| Secondary button | `#e8ece7`, `padding: 10px 14px`, same radius, no shadow |
| Drop / empty zone | `1.5px dashed #abb5ad`, `border-radius: 12px`, `background: #f7f9f5`; when filled → `border-style: solid`, `border-color: #8fb942`, `background: #f6fbe9` |
| Icon tile | 38×38, `border-radius: 10px`, white, `1px solid var(--line)`, `display: grid; place-items: center` |

## Motion

One rule, everywhere:

```css
transition: transform 150ms ease, box-shadow 150ms ease;
:hover { transform: translateY(-1px); }
:disabled { opacity: 0.72; cursor: wait; }   /* wait, not not-allowed, for in-flight work */
```

Nothing scales, nothing fades in. **A 1px lift is the entire hover vocabulary.** More than one motion
idiom in an app reads as two apps.

## Conventions worth copying

- `* { box-sizing: border-box; }` and `html, body { margin: 0; min-height: 100% }`.
- Semantic class names describing the **thing** (`.brand-subtitle`, `.drop-zone.has-file`,
  `.viewer-toolbar`), not the styling. A class named for its styling is a class that lies after the
  first redesign.
- State as a **second class on the same element** (`.drop-zone.has-file`), not a separate selector tree.
- Shared layout collapsed into one grouped rule — the many `display: flex; align-items: center`
  elements are declared together, then each gets only its own `gap`.
- Tailwind is imported (`@import "tailwindcss";`) but the app's own vocabulary lives in real CSS classes
  over these variables. Follow that: variables plus named classes, Tailwind for one-offs.

## What this theme is not

It is a **palette and a set of recipes**, not a component library. Copy the variables and the structural
recipes into the new app's own CSS; do not add a dependency to share them. And note the product this
came from is Docker/compose-based — **do not copy its infra shape** into a lambda service.
