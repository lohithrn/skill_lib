---
name: md_deck-builder
description: "Modernize or build a branded PowerPoint deck by editing your own template in place, so all branding (footer chrome, title/subtitle styling, section and closing slides) is inherited natively rather than redrawn. Use this skill when the user provides a starter/vanilla PPTX to make client-ready and on-brand, or wants a new branded deck built from an outline or content. The skill duplicates the template's blank content slide for each content slide needed, keeps the title/section/closing slides intact (text edits only), and restyles white bullet-wall content into card rows, branded tables, stat callouts, and comparison layouts using the token palette read out of the template. Triggers: 'make this deck on-brand', 'modernize this PPTX', 'build a deck from this outline', 'this deck is a wall of bullets', 'put our branding on these slides'."
when_to_use: A PPTX must be built or restyled against a template whose branding must survive exactly.
argument-hint: "[source.pptx | an outline] — plus the path to your template"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Deck Builder / Modernizer

Build or modernize a branded deck by **editing your own template in place** — never by rebuilding from scratch. This preserves branding exactly, because the footer, title styling, section slides, and closing slide all come from the real template.

## The gate — read this first

**No template, no deck.** This skill ships no template and no brand assets: you supply your own PPTX and configure its path (this file assumes `assets/template.pptx`; use whatever path you like). Introspect it before you build — the layout numbers, colours, fonts and placeholder geometry in `references/template_spec.md` are **placeholders describing a reference template**, not your brand. Building from the placeholder values ships an off-brand deck.

**The palette, fonts and layout indices are inputs, not constants.** Read them out of your template once, write them down, then build.

## Core principle: edit the template, don't recreate it

The #1 lesson from every prior deck: **branding that is drawn by hand drifts and looks off.** The footer (wordmark + accent chevron + confidentiality line + page number) is inherited from the content layout. Duplicate real template slides and inherit — do not draw footers, and do not rebuild the title/section/closing slides.

## The template you supply

A 5-slide, 13.33" × 7.5" (LAYOUT_WIDE) deck. Each slide has a role; the layout numbers below are the reference template's, so map yours once and use your own numbers everywhere after.

| Slide | Layout | Role | How to use |
|---|---|---|---|
| 1 | 13 | **Title** (dark, logo, hero image, accent tagline) | Edit text only — keep the design |
| 2 | 12 | **Blank content** (title + accent subtitle placeholders, footer inherited) | **Duplicate this** once per content slide; add restyled body shapes |
| 3 | 15 | **Section divider** — "Section Title" only | Edit text only; use to open a multi-section deck |
| 4 | 16 | **Section divider + caption** — "Section Title" + "Optional Caption" | Edit text only; alternative divider |
| 5 | 14 | **Closing / capstone** (THANK YOU, offices, contact) | Edit text only, or leave as-is |

Slides 1, 3, 4, 5 are **never recreated** — text edits only. Slide 2 is the only one you duplicate and fill.

## Workflow

1. **Read the template spec first:** `references/template_spec.md`. It says what to extract from your template and what each token is for — do not brand from memory.
2. **Extract the source content** (if modernizing an existing deck): `markitdown source.pptx` for text; render to images for layout context (see `references/iteration_checklist.md`).
3. **Plan the slide map.** Decide which content sections become content slides. **Preserve any section-divider slides that already exist** (see HARD RULES). For a new ~**8**+ slide deck with distinct sections, plan where dividers go — do not omit them on a long, multi-section deck.
4. **Do all structural work before editing content:** unpack the template, duplicate the blank content slide once per content slide using `scripts/duplicate_content_slide.py` (or `add_slide.py` from the public pptx skill), KEEP the divider slides and the title/closing slides, reorder `<p:sldIdLst>`, then `clean.py`.
5. **Fill each content slide — TITLE first, then SUBTITLE, then BODY. This order is mandatory.**
   - **TITLE (required, NEVER empty):** every content slide MUST have its title placeholder populated with a short **ALL-CAPS section headline** (e.g. `THE WINDOW WE'RE TRYING TO CLOSE`). This is the headline, not the tagline. An empty title = a broken slide. Set it with `swap_title()` from `ooxml_helpers.py`, or write the run into the title `<p:ph>`'s `<a:t>` directly. Do this for EVERY content slide before moving on.
   - **SUBTITLE (optional, one line):** the accent subtitle placeholder (**18pt**, the template's accent colour) holds a one-line tagline/framing (e.g. `This is a retention decision — not a cold pitch`).
   - **⚠ The #1 mistake:** putting the tagline in the TITLE slot and leaving the real headline blank. TITLE = ALL-CAPS headline; SUBTITLE = accent one-liner. They are different placeholders with different content — never swap them.
   - **BODY:** add restyled shapes below using patterns from `references/layout_patterns.md`. Embed any icons as slide-relationship media.
6. **Edit title/section/closing text** directly in the title, divider and closing slides — swap their text, never restructure or delete them.
7. **QA GATE (required, blocking):** run `python scripts/qa_gate.py out.pptx --source <template_or_source>.pptx`. It FAILS the build if any content-slide title is empty, if a title merely duplicates its subtitle, if section dividers present in the source were stripped, or if divider subtitles are inconsistent (some have a caption, some don't). **Do not declare the deck done until this passes.** Then validate against the template and run the visual QA in `references/iteration_checklist.md`.

## HARD RULES (violations = broken deck)

- **Every content slide has a populated ALL-CAPS title.** Never leave the title placeholder empty; never put the subtitle text in it.
- **Never strip section dividers.** If the source/template has divider slides, they MUST survive into the output. Only ADD dividers, never remove — a short single-flow deck under ~**8** slides simply has none to begin with.
- **Section dividers must be CONSISTENT — treat them as a set.** Every divider gets a populated title (`OPPORTUNITY A`, etc.). Then decide once, for the whole deck: either ALL dividers carry a one-line subtitle/caption, or NONE do. Never mix. Both divider layouts have a caption placeholder, so a title-only divider is a *choice not to fill it*, not a limitation. If you give one divider a subtitle, give them all one — and where the source didn't supply text for a section (e.g. Opportunity A), **infer a subtitle from that section's own content slides** (e.g. "Personalization & Evaluation Platform" pulled from the section's lead slide). Consistency across dividers matters more than any single source gap.
- **Preserve divider descriptors from the source — don't drop them.** Source decks often encode the section descriptor *inside the title* as `OPPORTUNITY B — MIGRATION & RE-ARCHITECTURE`. Split that into title (`OPPORTUNITY B`) + subtitle (`Migration & Re-architecture`) — never keep the title and silently discard the descriptor. `scripts/qa_gate.py` compares source→output and FAILS if a source divider's descriptor words survive nowhere.
- **Adding a divider subtitle = adding a placeholder shape, not filling an empty one.** A title-only divider slide often has NO body placeholder instantiated in its XML (just the title `<p:sp>`). To add a subtitle you must copy the body/subtitle `<p:sp>` from a divider that has one (or from the layout) into the slide's `<p:spTree>`, then set its text — you can't fill a slot that isn't there.
- **Never draw the footer or hardcode page numbers** — inherit from the content layout.
- **Title / section / closing slides are text-edits only** — never recreated or deleted.

## Mechanics reference

Follow the public **pptx** skill for the unpack → edit → repack pipeline, `add_slide.py`, `clean.py`, `validate.py`, and image rendering; it is normally mounted at `/mnt/skills/public/pptx/`. This skill layers the template-driven token system and layout patterns on top.

Key commands:
```bash
# unpack
python3 -c "import zipfile; zipfile.ZipFile('template.pptx').extractall('unpacked')"
# duplicate the blank content slide — do all duplications BEFORE editing content
python /mnt/skills/public/pptx/scripts/add_slide.py unpacked/ slide2.xml --after slide2.xml
# ... reorder <p:sldIdLst> in ppt/presentation.xml, then:
python /mnt/skills/public/pptx/scripts/clean.py unpacked/
# repack (from INSIDE the dir)
(cd unpacked && rm -f ../out.pptx && zip -Xr ../out.pptx .)
# validate against the template so inherited template quirks are baselined out
python /mnt/skills/public/pptx/scripts/office/validate.py out.pptx --original template.pptx
```

## Index

| File | What it answers |
|---|---|
| `references/template_spec.md` | What to extract from your template — token palette, fonts, placeholder geometry, footer inheritance, the five slide roles. **Read first.** |
| `references/design_principles.md` | The anti-generic do/don't list — 11 rules plus the AI-tell avoidance list. |
| `references/layout_patterns.md` | The **7** high-value content-slide patterns, with coordinates and OOXML. |
| `references/iteration_checklist.md` | Visual, file and content QA before declaring done. |
| `scripts/qa_gate.py` | **Blocking** structural check: titles populated, ALL-CAPS, dividers preserved and consistent. Run before done. |
| `scripts/ooxml_helpers.py` | Shape-builder atoms — `rrect()`, `rect()`, `ellipse()`, `txt()`, `pic()`, `icon_chip()`, `swap_title()`, `check_bounds()`. |
| `scripts/duplicate_content_slide.py` | Duplicate the blank content slide N× before any content editing. |

## What this does NOT do

- **It does not ship a template, a logo, a font or an icon set.** Supply your own template at the path you configure; nothing branded is bundled, so nothing branded can be leaked or go stale.
- **It does not draw branding.** No hand-drawn footer, no hardcoded page number, no redrawn title slide. Anything the layout can inherit is inherited, because hand-drawn chrome drifts the moment a slide is inserted.
- **It does not batch.** One deck at a time, driven by design judgment. Source decks vary too widely for a deterministic pipeline; the references guide the judgment and the scripts supply the primitives.
- **It does not declare done on a render.** `scripts/qa_gate.py` is blocking and non-zero means not done — a good-looking PDF with an empty title placeholder is still a broken deck.
- **It does not invent brand values.** If the template does not state a colour, a font or a geometry, extract it or ask — never guess a hex.
