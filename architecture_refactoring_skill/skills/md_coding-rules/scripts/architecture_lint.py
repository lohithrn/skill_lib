#!/usr/bin/env python3
"""
architecture_lint.py
====================

Deterministic pre-pass for the `coding-rules` review skill.

SKILL.md is mostly judgment: responsibility boundaries, dependency injection,
polymorphism, over-engineering. A handful of its rules, though, are *countable*
— and an AI eyeballing line counts is slower and less reliable than a scanner.
This tool measures exactly those mechanical rules so the review starts from hard
facts and the AI spends its attention on the judgment calls:

  - File over 250 lines            (SKILL.md rule 3)
  - Method/function over 25 lines  (SKILL.md rule 4)
  - Loop body over 8 lines         (SKILL.md rule 5)
  - Vague file / folder names       (SKILL.md rules 1, 2)
  - Vague method names              (SKILL.md rule 7F)
  - Single-member (str, Enum)       (SKILL.md rule 7A)
  - Module-level mutable globals    (SKILL.md rule 21)

It is intentionally CONSERVATIVE: it reports only what it can measure without
guessing intent, and it never edits code. SKILL.md runs it first, then the
skill's reviewer reasons about everything the scanner cannot see.

Scope selection, in priority order:
  1. explicit paths passed as arguments
  2. --changed  -> files changed in the current git working tree
  3. interactive prompt (a path, or blank = the git working tree)

Output is a grouped human report by default, or JSON with --json (what the
command consumes to drive the review).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from lint_model import (
    Finding, MAX_FILE_LINES, SKIP_DIRS, VAGUE_DIR_NAMES, VAGUE_FILE_STEMS,
)
from python_structure_checks import check_python_module


# --------------------------------------------------------------------------- #
# IO helpers (match the house style used by the other scripts in this skill)
# --------------------------------------------------------------------------- #
def color(text: str, code: str) -> str:
    return text if not sys.stdout.isatty() else f"\033[{code}m{text}\033[0m"


def info(message: str) -> None:
    print(color(f"▸ {message}", "36"), file=sys.stderr)


def warn(message: str) -> None:
    print(color(f"⚠ {message}", "33"), file=sys.stderr)


def die(message: str, code: int = 1) -> "NoReturn":  # type: ignore[valid-type]
    print(color(f"✖ {message}", "31"), file=sys.stderr)
    sys.exit(code)


# --------------------------------------------------------------------------- #
# Target discovery
# --------------------------------------------------------------------------- #
def changed_files() -> list[Path]:
    """Files touched in the git working tree (tracked changes + untracked)."""
    try:
        tracked = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return []
    return [Path(p) for p in dict.fromkeys(tracked + untracked) if Path(p).is_file()]


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def expand_paths(paths: list[Path]) -> list[Path]:
    """Turn a mix of files and directories into a de-duplicated file list."""
    files: dict[Path, None] = {}
    for path in paths:
        for resolved in _files_under(path):
            files[resolved] = None
    return list(files)


def _files_under(path: Path) -> list[Path]:
    """The reviewable files a single argument expands to (file, or dir tree)."""
    if path.is_dir():
        return [c for c in sorted(path.rglob("*")) if c.is_file() and not is_skipped(c)]
    if path.is_file() and not is_skipped(path):
        return [path]
    return []


# --------------------------------------------------------------------------- #
# Language-agnostic file-level checks
# --------------------------------------------------------------------------- #
def check_file_length(path: Path, line_count: int) -> list[Finding]:
    if line_count <= MAX_FILE_LINES:
        return []
    return [Finding(
        str(path), 1, "file-too-long", "warning",
        f"File is {line_count} lines (> {MAX_FILE_LINES}). "
        "Split by responsibility (SKILL.md rule 3).",
    )]


def check_vague_path(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    if path.stem.lower() in VAGUE_FILE_STEMS:
        findings.append(Finding(
            str(path), 1, "vague-file-name", "info",
            f"File name '{path.name}' is vague. Prefer a responsibility-based "
            "name like 'stripe_payment_processor' (SKILL.md rule 2).",
        ))
    vague_dir = next((p for p in path.parts[:-1] if p.lower() in VAGUE_DIR_NAMES), None)
    if vague_dir:
        findings.append(Finding(
            str(path), 1, "vague-folder-name", "info",
            f"Folder '{vague_dir}' is a catch-all. Split into responsibility-based "
            "folders (SKILL.md rule 1).",
        ))
    return findings


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def scan_file(path: Path) -> list[Finding]:
    try:
        source = path.read_text(errors="ignore")
    except OSError:
        return []
    line_count = source.count("\n") + 1 if source else 0
    findings = check_file_length(path, line_count)
    findings.extend(check_vague_path(path))
    if path.suffix == ".py":
        findings.extend(check_python_module(path, source, warn))
    return findings


def scan(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in expand_paths(paths):
        findings.extend(scan_file(path))
    findings.sort(key=lambda f: (f.file, f.line, f.rule))
    return findings


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
SEVERITY_CODE = {"warning": "33", "info": "36"}


def print_report(findings: list[Finding]) -> None:
    if not findings:
        print(color("✔ No mechanical architecture violations found. "
                     "Proceed to the judgment-based review.", "32"))
        return
    current_file = None
    for finding in findings:
        if finding.file != current_file:
            current_file = finding.file
            print("\n" + color(current_file, "1"))
        marker = color(f"  {finding.severity.upper():7}",
                       SEVERITY_CODE.get(finding.severity, "0"))
        print(f"{marker} L{finding.line:<4} [{finding.rule}] {finding.message}")
    warnings = sum(1 for f in findings if f.severity == "warning")
    print("\n" + color(
        f"{len(findings)} finding(s): {warnings} warning(s), "
        f"{len(findings) - warnings} info.", "35"))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def resolve_targets(args: argparse.Namespace) -> list[Path]:
    if args.paths:
        return [Path(p) for p in args.paths]
    if args.changed:
        return changed_files() or die("No changed files in the git working tree.")
    if not sys.stdin.isatty():
        return changed_files() or die("No paths given and nothing changed in git.")
    answer = input(color("? Path to review (blank = git working tree): ", "1")).strip()
    if not answer:
        return changed_files() or die("Nothing changed in the git working tree.")
    return [Path(answer)]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="architecture_lint.py",
        description="Deterministic pre-pass for the coding-rules skill — measures "
                    "the countable SKILL.md rules (file/method/loop size, vague "
                    "names, single-member enums, module state). Never edits code.",
    )
    parser.add_argument("paths", nargs="*", help="Files or directories to scan.")
    parser.add_argument("--changed", action="store_true",
                        help="Scan files changed in the git working tree.")
    parser.add_argument("--json", action="store_true",
                        help="Emit findings as JSON (consumed by the review flow "
                             "in SKILL.md).")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    findings = scan(resolve_targets(args))
    if args.json:
        print(json.dumps({"findings": [asdict(f) for f in findings]}, indent=2))
    else:
        print_report(findings)
    # Exit non-zero only on hard size violations so CI can gate on them; info
    # findings never fail the run.
    sys.exit(1 if any(f.severity == "warning" for f in findings) else 0)


if __name__ == "__main__":
    main()
