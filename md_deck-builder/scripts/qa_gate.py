#!/usr/bin/env python3
"""Hard QA gate for deck-builder output. Exits non-zero (build is NOT done)
if any structural rule is violated. Run BEFORE declaring a deck finished.

Checks:
  1. Every content slide has a NON-EMPTY title placeholder.
  2. The title is not merely a duplicate of the subtitle (tagline-in-title bug).
  3. Section-divider slides present in the SOURCE are still present in OUTPUT
     (dividers were not stripped).
  4. Divider descriptor content in the SOURCE survives on some output divider
     (a 'TITLE - DESCRIPTOR' section header must not lose its descriptor).
  5. Dividers are internally consistent: every divider has a title, and
     subtitles/captions are all-or-none across the set.
  6. Title slide and closing slide are still present.

The layout indices below are the reference template's. Your template WILL number
its layouts differently; pass the flags or the gate matches no slides and passes
without checking anything.

Usage:
    python qa_gate.py <output.pptx> [--source <original_or_template.pptx>]
                      [--content-layout 12] [--title-layout 13]
                      [--closing-layout 14] [--divider-layouts 15,16]
"""
import sys, re, zipfile, os

CONTENT_LAYOUT = "slideLayout12.xml"
DIVIDER_LAYOUTS = {"slideLayout15.xml", "slideLayout16.xml"}
TITLE_LAYOUT = "slideLayout13.xml"
CLOSING_LAYOUT = "slideLayout14.xml"

def layout_name(value):
    """Accept `12`, `slideLayout12` or `slideLayout12.xml`; return the file name."""
    value = str(value).strip()
    if value.isdigit():
        value = "slideLayout" + value
    return value if value.endswith(".xml") else value + ".xml"

def flag(argv, name):
    """Value of `--name V`, or None. A flag with no value is an error, not a default."""
    if name not in argv:
        return None
    index = argv.index(name) + 1
    if index >= len(argv):
        print(f"{name} needs a value"); sys.exit(2)
    return argv[index]

def slide_layout_map(pptx):
    z = zipfile.ZipFile(pptx)
    names = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
    out = {}
    for n in names:
        base = os.path.basename(n)
        rels = z.read(f"ppt/slides/_rels/{base}.rels").decode("utf-8", "ignore")
        m = re.search(r"(slideLayout\d+\.xml)", rels)
        out[base] = (m.group(1) if m else "?", z.read(n).decode("utf-8", "ignore"))
    return out

def title_text(xml):
    m = re.search(r'<p:ph type="title".*?</p:sp>', xml, re.S)
    if not m: return None  # no title placeholder at all
    ts = re.findall(r'<a:t>([^<]*)</a:t>', m.group(0))
    return "".join(ts).strip()

def subtitle_text(xml):
    m = re.search(r'<p:ph type="body".*?</p:sp>', xml, re.S)
    if not m: return None
    ts = re.findall(r'<a:t>([^<]*)</a:t>', m.group(0))
    return "".join(ts).strip()

def _all_slides(pptx):
    z = zipfile.ZipFile(pptx)
    names = sorted([n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
                   key=lambda s: int(re.search(r'\d+', s).group()))
    return [(os.path.basename(n), z.read(n).decode("utf-8", "ignore")) for n in names]

def _divider_texts(pptx):
    """Layout-agnostic: a divider is a slide whose title starts with a section
    marker (OPPORTUNITY / SECTION / PART / PHASE) and has little other text.
    Returns list of (base, title, joined_all_text). Works across templates
    where source and output use different divider layout numbers."""
    res = []
    for b, xml in _all_slides(pptx):
        ts = re.findall(r'<a:t>([^<]*)</a:t>', xml)
        m = re.search(r'<p:ph type="title".*?<a:t>([^<]*)</a:t>', xml, re.S)
        title = m.group(1) if m else ""
        if re.match(r'\s*(OPPORTUNITY|SECTION|PART|PHASE)\b', title, re.I) and len(ts) <= 4:
            res.append((b, title, " ".join(ts)))
    return res

def _descriptor_words(t):
    t = t.replace("&amp;", "and")
    stop = {"opportunity", "section", "part", "phase"}
    return set(w for w in re.findall(r'[a-z0-9]+', t.lower()) if len(w) > 3 and w not in stop)

def main():
    global CONTENT_LAYOUT, DIVIDER_LAYOUTS, TITLE_LAYOUT, CLOSING_LAYOUT
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    out = sys.argv[1]
    src = flag(sys.argv, "--source")
    CONTENT_LAYOUT = layout_name(flag(sys.argv, "--content-layout") or CONTENT_LAYOUT)
    TITLE_LAYOUT = layout_name(flag(sys.argv, "--title-layout") or TITLE_LAYOUT)
    CLOSING_LAYOUT = layout_name(flag(sys.argv, "--closing-layout") or CLOSING_LAYOUT)
    dividers_flag = flag(sys.argv, "--divider-layouts")
    if dividers_flag:
        DIVIDER_LAYOUTS = {layout_name(v) for v in dividers_flag.split(",") if v.strip()}

    om = slide_layout_map(out)
    fails = []

    content = [(b, xml) for b,(lay,xml) in om.items() if lay == CONTENT_LAYOUT]
    if not content:
        fails.append(f"NO slide uses {CONTENT_LAYOUT}: wrong --content-layout, so nothing was checked")
    for b, xml in sorted(content):
        t = title_text(xml)
        sub = subtitle_text(xml)
        if t is None:
            fails.append(f"{b}: NO title placeholder (content slide must have one)")
        elif t == "":
            fails.append(f"{b}: EMPTY title (must be an ALL-CAPS section headline)")
        elif sub and t == sub:
            fails.append(f"{b}: title == subtitle ('{t[:40]}') - tagline was put in the title slot")
        elif t and t != t.upper() and len(t) > 3:
            fails.append(f"{b}: title not ALL-CAPS ('{t[:40]}') - content titles are ALL-CAPS")

    if src and os.path.exists(src):
        sm = slide_layout_map(src)
        src_div = sum(1 for _,(lay,_) in sm.items() if lay in DIVIDER_LAYOUTS)
        out_div = sum(1 for _,(lay,_) in om.items() if lay in DIVIDER_LAYOUTS)
        if src_div > 0 and out_div < src_div:
            fails.append(f"DIVIDERS STRIPPED: source had {src_div} divider slide(s), output has {out_div}")

        # Content-loss: descriptor text on a SOURCE divider must survive somewhere
        # on the OUTPUT dividers (title OR subtitle). Layout-agnostic so it works
        # even when source/output use different divider layout numbers.
        src_divs = _divider_texts(src)
        out_divs = _divider_texts(out)
        out_words = set()
        for _, _, joined in out_divs:
            out_words |= _descriptor_words(joined)
        for b, title, joined in src_divs:
            missing = _descriptor_words(joined) - out_words
            if missing:
                fails.append(
                    f"DIVIDER CONTENT LOST from source {b} ({title!r}): descriptor words "
                    f"{sorted(missing)} appear on no output divider. Preserve the section "
                    f"descriptor as the divider's subtitle (split 'TITLE - DESCRIPTOR' into "
                    f"title + subtitle), don't drop it."
                )

    # Divider consistency: every divider must have a NON-EMPTY title, and
    # captions/subtitles must be all-or-none across all dividers.
    dividers = [(b, xml) for b,(lay,xml) in sorted(om.items()) if lay in DIVIDER_LAYOUTS]
    cap_flags = []
    for b, xml in dividers:
        dt = title_text(xml)
        dc = subtitle_text(xml)  # body placeholder = the caption/subtitle slot
        if not dt:
            fails.append(f"{b}: DIVIDER has empty title (section dividers need a title)")
        cap_flags.append(bool(dc))
    if dividers and any(cap_flags) and not all(cap_flags):
        with_cap = [b for (b, _), f in zip(dividers, cap_flags) if f]
        without = [b for (b, _), f in zip(dividers, cap_flags) if not f]
        fails.append(
            "DIVIDER SUBTITLES INCONSISTENT: captions must be all-or-none across dividers. "
            f"With caption: {', '.join(with_cap)}. Missing: {', '.join(without)}. "
            "Add an inferred subtitle to the missing ones (draw it from that section's content), "
            "or remove captions from all dividers."
        )

    if not any(lay == TITLE_LAYOUT for _,(lay,_) in om.items()):
        fails.append(f"TITLE slide ({TITLE_LAYOUT}) missing from output")
    if not any(lay == CLOSING_LAYOUT for _,(lay,_) in om.items()):
        fails.append(f"CLOSING slide ({CLOSING_LAYOUT}) missing from output")

    if fails:
        print("QA GATE FAILED:")
        for f in fails: print("  X", f)
        sys.exit(1)
    print("QA GATE PASSED: titles populated, dividers preserved & consistent, title/closing present.")

if __name__ == "__main__":
    main()
