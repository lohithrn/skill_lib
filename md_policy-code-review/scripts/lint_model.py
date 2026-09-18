"""
lint_model.py
=============

The vocabulary of the architecture linter: the `Finding` result type plus the
thresholds and vague-name sets that the checks compare against. These mirror
SKILL.md exactly, so a rule-limit change is a one-line edit here rather than a
hunt through the checking code.
"""

from __future__ import annotations

from dataclasses import dataclass

# Size thresholds — mirror SKILL.md rules 3, 4, 5 exactly.
MAX_FILE_LINES = 250
MAX_METHOD_LINES = 25
MAX_LOOP_BODY_LINES = 8

# Vague names the skill calls out. File stems and folder names match
# case-insensitively; a method matches when its whole name is in the set.
VAGUE_FILE_STEMS = {
    "processor", "handler", "service", "manager", "helper", "helpers",
    "utils", "util", "common", "base", "logic", "misc", "stuff",
}
VAGUE_DIR_NAMES = {"utils", "helpers", "common", "misc", "util"}
VAGUE_METHOD_NAMES = {
    "do", "run", "execute", "handle", "process", "query", "_do_stuff",
    "_handle", "_process", "_execute", "_finalize", "_check", "_helper",
    "_do_it", "_do", "_stuff",
}

# Directories and generated files the scanner never descends into / reads.
SKIP_DIRS = {".git", ".terraform", "node_modules", "__pycache__", ".venv",
             "venv", ".mypy_cache", ".pytest_cache", "dist", "build"}


@dataclass(frozen=True)
class Finding:
    """One rule violation at a specific location. Serializable for --json."""
    file: str
    line: int
    rule: str
    severity: str
    message: str
