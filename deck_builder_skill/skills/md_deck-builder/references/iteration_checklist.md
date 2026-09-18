# Iteration Checklist — QA before declaring done

Run all of this. First render usually has 1–2 real issues; fix and re-render only what changed.

## QA GATE — run FIRST, it is blocking

```bash
python scripts/qa_gate.py out.pptx --source <template_or_source>.pptx
```

This must PASS before any other QA. It exits non-zero (build not done) if:

- any content slide has an EMPTY title placeholder,
- a content slide's title merely duplicates its subtitle (tagline-in-title bug),
- a content slide's title is not ALL-CAPS,
- section-divider slides present in the source were stripped from the output,
- a source divider's descriptor words survive on no output divider,
- divider captions are not all-or-none across the divider set,
- the title slide or closing slide went missing.

If your template's layout numbers differ from the defaults, pass `--content-layout`,
`--title-layout`, `--closing-layout` and `--divider-layouts` — otherwise the gate matches no slides
and passes without checking anything.

If it fails, fix the flagged slides and re-run. Only proceed to visual/file QA once it passes.

## Render to images

```bash
python /mnt/skills/public/pptx/scripts/office/soffice.py --headless --convert-to pdf out.pptx
rm -f slide-*.jpg
pdftoppm -jpeg -r 150 out.pdf slide
ls -1 "$PWD"/slide-*.jpg   # pass these paths to the view tool
```

## File validation (required)

```bash
python /mnt/skills/public/pptx/scripts/office/validate.py out.pptx --original template.pptx
```

Pass `--original template.pptx` so the template's own inherited quirks are baselined out and only
*your* regressions show. Fix any relationship / content-type / unreferenced-media errors (run
`clean.py` after slide deletions to clear orphaned media).

## Content check

```bash
markitdown out.pptx | grep -iE "\bx{3,}\b|lorem|ipsum|\bTODO|\[insert|Section Title|Optional Caption|Title Slide"
```

If any template placeholder text ("Section Title", "Optional Caption", your template's own title-slide
boilerplate) survives on a slide you meant to fill, fix it.

## Visual defects to look for (per slide)

- **Text overflow / cut off at a box or slide edge** — most common; check first.
- Footer overflow or content colliding with the inherited footer (keep body above ~**6.5"**).
- Layout bleed-through — a template layout shape showing where you didn't expect it.
- Table rows wrapping to two lines (tighten text or widen column — single-line cells only).
- Overlapping elements; uneven gaps; cards nearly touching (<**0.3"**).
- Low-contrast icons (dark icon on dark chip) or text (light on light).
- Hardcoded page numbers that don't match slide order (should never happen — use the inherited field).
- Section/title/closing slides accidentally restructured (they should be text-edits only).

## Branding check

- Every colour on the slide is a token from `template_spec.md` with your template's real value — not
  a placeholder hex, and not the theme accent when the subtitle states a different one.
- Content titles are the native **24pt** bold ALL-CAPS placeholder; subtitle is the **18pt** accent
  placeholder.
- Footer present and correct on every content slide (inherited, not drawn).
- Title / section / closing slides visually unchanged except their text.

## Bounds sanity (quick programmatic check)

For each restyled content slide, confirm every shape's `off + ext` is within 0–**12192000** (x) and
0–**6858000** (y) EMU. A shape past the edge is written but invisible. `check_bounds()` in
`scripts/ooxml_helpers.py` returns the offenders in inches.
