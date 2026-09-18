#!/usr/bin/env bash
# caps.sh — measure the hard limits. Router only: one scanner per language family.
#
# Emits one JSON object on stdout. Every number comes from a scan; nothing is estimated.
# Exit 0 = scan completed (violations are DATA, not failure). Exit 2 = could not scan.
#
# The scanners live in lib/ and emit JSONL violations on stdout, one per line:
#   {"file":"..","line":N,"metric":"..","value":N,"cap":N,"severity":"..","name":".."}
#
# Four responsibilities, four files, because this script was over its own 250-line cap:
#   lib/caps_files.sh    WHICH files may be measured, and the path-safety trust boundary
#   lib/caps_folders.sh  the one cap whose subject is a DIRECTORY, not a file
#   lib/caps_report.sh   HOW a finished scan is rendered (json, text)
#   this file            the caps themselves, and the order the scanners run in

set -uo pipefail

# The scanners import each other, so python would drop `__pycache__/` into the installed skill
# directory — a measurement tool that writes to the tree it was copied into. Nothing here is hot
# enough for the cache to matter.
export PYTHONDONTWRITEBYTECODE=1

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LIB="$HERE/lib"

# Sourced, not optional. Without either half this script cannot produce a correct answer, so a
# missing part is exit 2 rather than a degraded scan: "no scanner" and "nothing wrong" must never
# render the same, and that includes the case where the scanner itself is incomplete.
for part in caps_files.sh caps_folders.sh caps_report.sh; do
  [ -f "$LIB/$part" ] || { printf 'caps.sh: missing required part: lib/%s\n' "$part" >&2; exit 2; }
  # shellcheck source=/dev/null
  . "$LIB/$part"
done

# ---- caps: a knob per limit. Overridable so a repo can tighten, never loosen silently. ----
CAP_FILE_WARN="${CG_CAP_FILE_WARN:-200}"
CAP_FILE="${CG_CAP_FILE:-250}"
CAP_METHOD_WARN="${CG_CAP_METHOD_WARN:-15}"
CAP_METHOD="${CG_CAP_METHOD:-25}"
CAP_NESTING="${CG_CAP_NESTING:-1}"
CAP_LOOP_BODY="${CG_CAP_LOOP_BODY:-8}"
CAP_PARAMS_WARN="${CG_CAP_PARAMS_WARN:-3}"
CAP_PARAMS="${CG_CAP_PARAMS:-4}"
CAP_PUBLIC_WARN="${CG_CAP_PUBLIC_WARN:-5}"
CAP_PUBLIC="${CG_CAP_PUBLIC:-7}"
CAP_FOLDER_WARN="${CG_CAP_FOLDER_WARN:-5}"
CAP_FOLDER="${CG_CAP_FOLDER:-7}"

ROOT="."
FORMAT="json"
EXCLUDE_EXTRA=""

usage() {
  cat <<'EOF'
caps.sh — measure file length, files per folder, method length, nesting, loop bodies, else, params,
public members.

  caps.sh [--root PATH] [--json|--text] [--exclude REGEX] [--help]

Caps are read from the environment so they are one place, not scattered:
  CG_CAP_FILE=250 CG_CAP_FILE_WARN=200
  CG_CAP_METHOD=25 CG_CAP_METHOD_WARN=15
  CG_CAP_NESTING=1 CG_CAP_LOOP_BODY=8
  CG_CAP_PARAMS=4 CG_CAP_PARAMS_WARN=3
  CG_CAP_PUBLIC=7 CG_CAP_PUBLIC_WARN=5
  CG_CAP_FOLDER=7 CG_CAP_FOLDER_WARN=5

folder_files counts the code files DIRECTLY in one folder. Subfolders are never counted — a folder
may hold any number of folders, and nesting is the remedy the cap asks for. `.tf`/`.tfvars` are
excluded (in Terraform the directory IS the module, so the remedy is illegal) and so are `.h`/`.hpp`
(a header declares the answer its source defines). The reported path ends in `/` and line is 1: a
directory has no line. Exempt a folder with `codegraph:exempt folder_files -- <reason>` in a
`.codegraph-exempt` file inside it — a directory has no declaration to put a pragma above.

Nesting is measured FROM THE METHOD BODY: the outermost construct is depth 0, so `for` + `if` is
depth 1 and legal, and only a third level breaches. See SKILL.md "Hard limits".

A cap breach can be declared exempt in the source with a pragma that names the metrics and gives
a reason (`# codegraph:exempt nesting, loop_body -- <why>`); it is still reported, with severity
"exempt". A pragma with no reason suppresses nothing and is reported as exempt_without_reason.

Languages: python (AST-exact when python3 is present), typescript/javascript, java/kotlin, go
(brace scan). Anything else is counted for FILE LENGTH ONLY and listed under "degraded".

A violation is data, not an error: exit 0 with findings, exit 2 only if the scan could not run.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?--root needs a path}"; shift 2 ;;
    --json) FORMAT="json"; shift ;;
    --text) FORMAT="text"; shift ;;
    --exclude) EXCLUDE_EXTRA="${2:?--exclude needs a regex}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'caps.sh: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[ -d "$ROOT" ] || { printf 'caps.sh: not a directory: %s\n' "$ROOT" >&2; exit 2; }
ROOT="$(cd -- "$ROOT" && pwd)"

# An unparseable --exclude makes `grep` exit non-zero, and the `|| cat` fallback would then pass the
# UNFILTERED list through. Silently scanning what the caller asked to skip is worse than refusing.
if [ -n "$EXCLUDE_EXTRA" ]; then
  printf '' | grep -q -- "$EXCLUDE_EXTRA" 2>/dev/null
  [ $? -le 1 ] || { printf 'caps.sh: --exclude is not a valid regex: %s\n' "$EXCLUDE_EXTRA" >&2; exit 2; }
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/caps.XXXXXX")" || exit 2
trap 'rm -rf -- "$TMP"' EXIT
VIOL="$TMP/violations.jsonl"; : >"$VIOL"
DEGRADED="$TMP/degraded.txt"; : >"$DEGRADED"

# NOT `list_files | grep ...`: the left side of a pipe runs in a subshell, and the skip counters
# incremented there would be discarded — the caveats would silently vanish from `degraded`.
list_files >"$TMP/raw.txt"
grep -Ev "/($PRUNE_DIRS)/" "$TMP/raw.txt" \
  | { [ -n "$EXCLUDE_EXTRA" ] && grep -v -- "$EXCLUDE_EXTRA" || cat; } \
  | grep -Ev '\.(min\.js|lock|map|snap|png|jpg|jpeg|gif|svg|pdf|zip|gz|ico|woff2?|ttf)$' \
  > "$TMP/all.txt"

FIDELITY_FORCED="$(skip_notes)"

# "nothing scanned" and "nothing wrong" must never render the same. A clean report on an empty
# file list is the single most dangerous output this script could produce.
[ -s "$TMP/all.txt" ] || {
  printf 'caps.sh: no files to scan under %s\n' "$ROOT" >&2
  printf 'caps.sh: this is not a clean result — check --exclude, .gitignore and the path\n' >&2
  exit 2; }

pick() { grep -E "$1" "$TMP/all.txt" 2>/dev/null || true; }
pick '\.py$'                       > "$TMP/python.txt"
pick '\.(ts|tsx|js|jsx|mjs|cjs)$'  > "$TMP/ts.txt"
pick '\.(java|kt|kts)$'            > "$TMP/java.txt"
pick '\.go$'                       > "$TMP/go.txt"

# Every file we will judge on LENGTH: source in any language, first-class or not. Prose and data
# are excluded on purpose — the 250-line cap is a claim about how much CODE one file may hold, and
# firing it on a README or a fixture is a false finding that teaches a reader to ignore the tool.
CODE_RE='\.(py|pyi|ts|tsx|js|jsx|mjs|cjs|java|kt|kts|go|rb|rs|c|h|cc|cpp|hpp|cs|swift|scala|php|ex|exs|erl|clj|dart|sh|bash|zsh|awk|pl|lua|m|mm|groovy|gradle|tf|vue|svelte)$'
pick "$CODE_RE" > "$TMP/code.txt"

# ---- file length: one loop over the code list, read per file so no ARG_MAX and no `file(1)` ----
length_violation() {
  printf '{"file":"%s","line":1,"metric":"file_lines","value":%s,"cap":%s,"severity":"%s","name":""}\n' \
    "$1" "$2" "$3" "$4" >>"$VIOL"
}
# `lib/cap_pragma.py` attaches a pragma to the next DECLARATION below it, and a file has none — so
# a file-level exemption is read from the header instead: `# codegraph:exempt file_lines -- <reason>`
# in the first 20 lines. Same seam, same two conditions (name the metric, carry a reason), and the
# breach is still emitted with severity `exempt` so the report says what it suppressed.
head_exempts_length() {
  head -n 20 -- "$1" 2>/dev/null | grep -Eq \
    'codegraph:exempt[^-]*[[:space:],]file_lines([[:space:],][^-]*)?--[[:space:]]*[^[:space:]]'
}
classify_length() {
  head_exempts_length "$2" && { length_violation "$1" "$3" "$CAP_FILE" exempt; return 0; }
  [ "$3" -gt "$CAP_FILE" ] && { length_violation "$1" "$3" "$CAP_FILE" major; return 0; }
  length_violation "$1" "$3" "$CAP_FILE_WARN" minor
}
while IFS= read -r f; do
  [ -f "$f" ] || continue
  # NR, not `wc -l`: wc counts newlines, so a file with no final newline measures one line short
  # and a 251-line file lands as a 250-line minor — under the 250 hard cap it actually breaches.
  n=$(awk 'END{print NR+0}' <"$f")
  [ "$n" -gt "$CAP_FILE_WARN" ] || continue
  classify_length "$(jstr "${f#"$ROOT"/}")" "$f" "$n"
done <"$TMP/code.txt"

# ---- files per folder: the same list, grouped by directory instead of read per file -------------
# Runs before the language scanners so a folder finding is present even when every scanner degrades:
# the tree's shape is measurable from the file list alone, and it is the finding that most often
# explains the others (a 30-file folder is where the 400-line files accumulate).
scan_folders

# ---- python: exact, via the AST. No heuristic can match it, so prefer it hard. ----
FIDELITY="${FIDELITY_FORCED:-native}"
scan_python() {
  [ -s "$TMP/python.txt" ] || return 0
  command -v python3 >/dev/null 2>&1 && [ -f "$LIB/scan_python.py" ] || {
    echo "python: no python3 on PATH; python files counted for file length only" >>"$DEGRADED"
    FIDELITY="degraded"; return 0; }
  CG_CAP_METHOD="$CAP_METHOD" CG_CAP_METHOD_WARN="$CAP_METHOD_WARN" \
  CG_CAP_NESTING="$CAP_NESTING" CG_CAP_LOOP_BODY="$CAP_LOOP_BODY" \
  CG_CAP_PARAMS="$CAP_PARAMS" CG_CAP_PARAMS_WARN="$CAP_PARAMS_WARN" \
  CG_CAP_PUBLIC="$CAP_PUBLIC" CG_CAP_PUBLIC_WARN="$CAP_PUBLIC_WARN" \
  CG_ROOT="$ROOT" \
    python3 "$LIB/scan_python.py" <"$TMP/python.txt" >>"$VIOL" 2>"$TMP/py.err" || {
      echo "python: scanner failed ($(tr -d '\n' <"$TMP/py.err" | tail -c 200))" >>"$DEGRADED"
      FIDELITY="degraded"; }
}
scan_python

# ---- brace languages: one awk scanner, dialect passed in ----
scan_braces() {
  local list="$1" dialect="$2"
  [ -s "$list" ] || return 0
  if [ ! -f "$LIB/scan_braces.awk" ]; then
    echo "$dialect: lib/scan_braces.awk missing; file length only" >>"$DEGRADED"; FIDELITY="degraded"; return 0
  fi
  local rel
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    # `awk -v` runs ESCAPE PROCESSING on the value, so a file literally named `a\nb.ts` would put a
    # real newline inside FNAME and split the JSONL record in two. Double the backslashes and awk
    # collapses them back to the literal ones. Without this, a filename is a JSON injection point.
    rel="${f#"$ROOT"/}"
    rel="${rel//\\/\\\\}"
    awk -v FNAME="$rel" -v DIALECT="$dialect" \
        -v CAP_METHOD="$CAP_METHOD" -v CAP_METHOD_WARN="$CAP_METHOD_WARN" \
        -v CAP_NESTING="$CAP_NESTING" -v CAP_LOOP_BODY="$CAP_LOOP_BODY" \
        -v CAP_PARAMS="$CAP_PARAMS" -v CAP_PARAMS_WARN="$CAP_PARAMS_WARN" \
        -v CAP_PUBLIC="$CAP_PUBLIC" -v CAP_PUBLIC_WARN="$CAP_PUBLIC_WARN" \
        -f "$LIB/scan_braces.awk" "$f" >>"$VIOL" 2>/dev/null
  done <"$list"
}
scan_braces "$TMP/ts.txt"   "ts"
scan_braces "$TMP/java.txt" "java"
scan_braces "$TMP/go.txt"   "go"

# ---- other languages get file length only; say so rather than implying a clean scan ----
# A code file in a language we have no scanner for is measured for LENGTH ONLY. Say the number, so
# a reader can see how much of their repo the method/nesting/params findings actually cover.
if [ -s "$TMP/code.txt" ]; then
  others=$(grep -Ev '\.(py|pyi|ts|tsx|js|jsx|mjs|cjs|java|kt|kts|go)$' "$TMP/code.txt" | wc -l | tr -d ' ')
  [ "${others:-0}" -gt 0 ] && echo "$others code files in languages without a scanner: file length only" >>"$DEGRADED"
fi

# ---- a file the scanner could not read is a HOLE, not a clean result --------------------------
# `unparseable` and `unbalanced_braces` are already emitted per file, but a count buried in
# `totals` reads as one more minor. Fidelity is the field a gate looks at, so the fact that N files
# were never measured for method-level caps has to land there and in `degraded` too.
unreadable=$(grep -c '"metric":"\(unparseable\|unbalanced_braces\)"' "$VIOL" 2>/dev/null | tr -d ' ')
if [ "${unreadable:-0}" -gt 0 ]; then
  echo "$unreadable file(s) could not be parsed; they are counted for length only, not for method, nesting, params or public members" >>"$DEGRADED"
  FIDELITY="degraded"
fi

render "$FORMAT"
exit 0
