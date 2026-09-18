#!/usr/bin/env python3
"""Duplicate the blank content slide (slide2 in the reference template) N times
in your template, so you get N properly-footered content slides to fill.

This is a thin convenience wrapper around the public pptx skill's add_slide.py.
Do ALL duplication BEFORE editing any slide content (add_slide copies verbatim).

Usage:
    python duplicate_content_slide.py <unpacked_dir> <count> [--after slideN.xml]

Then edit ppt/presentation.xml <p:sldIdLst> to order the new slides, run
clean.py, fill each new slide's body via ooxml_helpers, and repack.

Set PPTX_SKILL_DIR if the public pptx skill is not at its default mount point.
"""
import subprocess, sys, os

PPTX_SKILL_DIR = os.environ.get("PPTX_SKILL_DIR", "/mnt/skills/public/pptx")
PUBLIC_ADD = os.path.join(PPTX_SKILL_DIR, "scripts", "add_slide.py")

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    unpacked = sys.argv[1]
    count = int(sys.argv[2])
    after = "slide2.xml"
    if "--after" in sys.argv:
        after = sys.argv[sys.argv.index("--after") + 1]
    if not os.path.exists(PUBLIC_ADD):
        print("ERROR: public add_slide.py not found at", PUBLIC_ADD)
        print("Point PPTX_SKILL_DIR at your checkout of the public pptx skill,")
        print("or duplicate slide2.xml manually with full package bookkeeping.")
        sys.exit(2)
    for i in range(count):
        # each new duplicate is inserted after the previous, preserving order
        subprocess.run(["python", PUBLIC_ADD, unpacked, "slide2.xml", "--after", after], check=True)
        # add_slide prints the created path; subsequent inserts go after slide2 too
    print(f"Duplicated content slide {count}x. Now edit <p:sldIdLst>, run clean.py, fill bodies.")

if __name__ == "__main__":
    main()
