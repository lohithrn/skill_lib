# Design Principles — branded decks

Hard-won lessons. These are the difference between a deck that looks AI-generated and one that looks
like your team made it.

## The 11 rules

1. **Never build from memory — introspect the actual template.** Layouts, placeholders, and
   layout-bleed shapes vary. Read `template_spec.md` and, when unsure, unpack the template and look.

2. **Content titles are near-black ALL-CAPS; subtitles carry the accent colour.** On the dark
   title/section/closing slides, titles are white/accent as the template already sets them — don't
   change that.

3. **Footer chrome is inherited from the content layout — never drawn manually.** Hardcoded footers
   and page numbers drift when slides are inserted/reordered. This bug bit past decks; the fix is
   native inheritance.

4. **No generic NxN identical-card grids.** They read as filler and have been rejected before. Use
   content-specific visualizations: lifecycle ribbons, role-kicker outcome columns, Today→Risk→Fix
   flows, Without/With comparisons, capability-badged tables, stat callouts.

5. **Differentiate parallel concepts with role labels, not just numbers.** "HOW WE BUILD IT" / "WHAT
   IT UNLOCKS" / "WHY IT MATTERS" beats "1 / 2 / 3".

6. **Tables:** dark header bar, capability color-coding, status pills (green/amber/purple),
   alternating row bands, single-line cells (no row wrapping). See `layout_patterns.md`.

7. **Preserve section dividers; only ever ADD them, never strip them. And keep them consistent as a
   set.** If the template or source deck already contains divider slides, they MUST remain in the
   output — removing them is a regression. For a NEW multi-section deck of ~**8**+ slides, insert
   dividers using the template's divider slides to open each section. **Consistency rule:** every
   divider gets a populated title, and subtitles/captions are all-or-none across the whole set —
   either every divider carries a one-line subtitle or none do, never a mix. Both divider layouts
   have a caption placeholder, so a bare divider is a choice, not a constraint; if you caption one,
   caption them all, inferring text from a section's own content where the source didn't provide it.
   Only a genuinely short (<**8** slide), single-flow deck has no dividers — because none were there
   to begin with, not because you removed them.

8. **Title, section, and closing slides stay as the template made them.** Text edits only. Never
   restructure or recreate them.

9. **Visual QA via PDF→JPG render is mandatory.** Check footer overflow, layout bleed-through, row
   wrapping, text overflow, low-contrast icons.

10. **Empty space is OK — don't pad to fill.** A clean slide with breathing room beats a crammed one.

11. **Content-slide titles are mandatory ALL-CAPS headlines — distinct from the accent subtitle.**
    Every content slide's title placeholder gets a short ALL-CAPS headline (e.g. "THE WINDOW WE'RE
    TRYING TO CLOSE"). The accent subtitle placeholder gets a one-line tagline. Never leave the title
    empty, and never put the tagline in the title slot — that is the single most common failure and
    it makes the whole deck look unfinished. `scripts/qa_gate.py` enforces this.

## AI-tell avoidance (from the public pptx skill, reinforced)

- **Never** put accent lines under titles, or decorative color bars / edge stripes / single-side
  borders on cards. To set a card apart use a subtle tint, a drop shadow, or an icon.
- Don't center body text — left-align paragraphs/lists; center only titles.
- Size contrast matters: titles **24pt**+ vs **12–14pt** body; big stats **34–40pt**.
- One color dominates (dark or white ground), the accent is the sharp accent — never give all colors
  equal weight.
- Icons on colored circles must be rendered **white** (an accent-coloured icon on an accent circle is
  invisible — this actually happened). Pre-render white + colored variants.

## Layout variety checklist

A strong content deck varies its layouts. Across the content slides, aim to use several of:

- icon-signal rows (icon chip + bold header + description)
- stat callout cards (big number + small label)
- labeled A/B/C option cards
- staged flow with arrows (Today → Risk → Fix)
- two-column comparison (Without / With, Before / After)
- branded table (objections, capabilities, status)
- a dark "why us / key point" band to anchor the argument

Don't repeat one layout on every slide.
