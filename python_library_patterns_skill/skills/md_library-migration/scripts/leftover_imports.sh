#!/usr/bin/env bash
#
# leftover_imports.sh — offline, stdlib-only. Answers exactly one question:
#
#   "Which import statements in this tree still name a module path I said I removed?"
#
# With no --prefix it instead inventories every module the tree imports, which is how you
# discover what a migration map has to cover before you write it.
#
# Read-only. Never writes, never resolves a name, never executes the code it reads. It is a
# lexical scan of import statements, so it cannot see a dynamic import; that limit is reported
# in "degraded" rather than hidden.
#
#   bash leftover_imports.sh --root . --prefix old.pkg.commons --json
#   bash leftover_imports.sh --root . --text
#
# Exit 0 whenever the scan ran, findings or not. Exit 2 only when it could not run.

set -uo pipefail

ROOT="."
FORMAT="json"
PREFIXES=()

usage() {
  cat <<'EOF'
leftover_imports.sh --root PATH [--prefix MODULE]... [--json|--text]

  --root PATH      tree to scan (default: .)
  --prefix MODULE  an old module path that must no longer be imported; repeatable
  --json           machine output (default)
  --text           human summary
  -h, --help       this message
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      ROOT="${2:?--root needs a path}"; shift 2 ;;
    --prefix)
      PREFIXES+=("${2:?--prefix needs a module path}"); shift 2 ;;
    --json)
      FORMAT="json"; shift ;;
    --text)
      FORMAT="text"; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ ! -d "$ROOT" ]; then
  printf 'not a directory: %s\n' "$ROOT" >&2
  exit 2
fi

command -v python3 >/dev/null 2>&1 || { printf 'python3 required\n' >&2; exit 2; }

python3 - "$ROOT" "$FORMAT" ${PREFIXES[@]+"${PREFIXES[@]}"} <<'PY'
import json
import os
import re
import sys

root = sys.argv[1]
fmt = sys.argv[2]
prefixes = [arg.strip() for arg in sys.argv[3:] if arg.strip()]

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox",
             ".mypy_cache", ".pytest_cache", "build", "dist", ".eggs"}
MAX_BYTES = 2 * 1024 * 1024
CONTROL = re.compile(r"[\x00-\x1f\x7f]")

# `from a.b import c` / `import a.b as d` / `import a.b, c.d`. Deliberately lexical: a dotted
# path inside a string or a comment is not an import and is not matched, and a name assembled
# at run time cannot be matched at all.
FROM_RE = re.compile(r"^\s*from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\b")
IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_][A-Za-z0-9_.,\s]*)")

degraded = []
skipped_control = 0
skipped_oversize = 0
skipped_unreadable = 0
skipped_links = 0

files_scanned = 0
statements = 0
counts = {}
files_per_module = {}
violations = []
files_with = set()


def matches(module):
    for p in prefixes:
        if module == p or module.startswith(p + "."):
            return p
    return None


for base, dirs, names in os.walk(root, followlinks=False):
    dirs[:] = sorted(d for d in dirs
                     if d not in SKIP_DIRS
                     and not os.path.islink(os.path.join(base, d))
                     and not CONTROL.search(d))
    for name in sorted(names):
        if not name.endswith(".py"):
            continue
        full = os.path.join(base, name)
        if os.path.islink(full):
            skipped_links += 1
            continue
        if CONTROL.search(name):
            skipped_control += 1
            continue
        try:
            if os.path.getsize(full) > MAX_BYTES:
                skipped_oversize += 1
                continue
            with open(full, encoding="utf-8", errors="replace") as handle:
                lines = handle.read().splitlines()
        except OSError:
            skipped_unreadable += 1
            continue
        files_scanned += 1
        rel = os.path.relpath(full, root)
        seen_here = set()
        for number, line in enumerate(lines, 1):
            found = FROM_RE.match(line)
            modules = []
            if found:
                modules = [found.group(1)]
            else:
                found = IMPORT_RE.match(line)
                if found:
                    for part in found.group(1).split(","):
                        part = part.strip().split(" as ")[0].strip()
                        if part:
                            modules.append(part)
            if not modules:
                continue
            statements += 1
            for module in modules:
                counts[module] = counts.get(module, 0) + 1
                if module not in seen_here:
                    seen_here.add(module)
                    files_per_module[module] = files_per_module.get(module, 0) + 1
                if matches(module):
                    violations.append({"file": rel, "line": number, "module": module,
                                       "statement": line.strip()[:160]})
                    files_with.add(rel)

if skipped_control:
    degraded.append("%d file(s) skipped: control character in the name" % skipped_control)
if skipped_oversize:
    degraded.append("%d file(s) skipped: larger than MAX_BYTES" % skipped_oversize)
if skipped_unreadable:
    degraded.append("%d file(s) skipped: unreadable" % skipped_unreadable)
if skipped_links:
    degraded.append("%d symlink(s) skipped: not followed out of the tree" % skipped_links)
degraded.append("lexical scan: a module named only at run time cannot be seen")

inventory = [{"module": m, "count": counts[m], "files": files_per_module.get(m, 0)}
             for m in sorted(counts, key=lambda k: (-counts[k], k))]

report = {
    "root": root,
    "prefixes": prefixes,
    "fidelity": "degraded" if (skipped_control or skipped_oversize or skipped_unreadable) else "native",
    "degraded": degraded,
    "totals": {
        "files_scanned": files_scanned,
        "import_statements": statements,
        "distinct_modules": len(counts),
        "violations": len(violations),
        "files_with_violations": len(files_with),
    },
    "violations": violations,
    "inventory": inventory,
}

if fmt == "text":
    out = []
    out.append("root=%s files=%d imports=%d modules=%d fidelity=%s"
               % (root, files_scanned, statements, len(counts), report["fidelity"]))
    if prefixes:
        out.append("prefixes: %s" % ", ".join(prefixes))
        out.append("LEFTOVER: %d import(s) in %d file(s)" % (len(violations), len(files_with)))
        for item in violations[:40]:
            out.append("  %s:%d  %s" % (item["file"], item["line"], item["statement"]))
        if len(violations) > 40:
            out.append("  ... %d more" % (len(violations) - 40))
    else:
        out.append("top imported modules:")
        for item in inventory[:40]:
            out.append("  %5d  %s  (%d file(s))" % (item["count"], item["module"], item["files"]))
    for note in degraded:
        out.append("degraded: %s" % note)
    print("\n".join(out))
else:
    print(json.dumps(report, indent=2, sort_keys=True))
PY
