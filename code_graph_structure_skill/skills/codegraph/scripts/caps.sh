#!/usr/bin/env bash
# caps.sh — measure the hard limits. Router only: one scanner per language family.
#
# Emits one JSON object on stdout. Every number comes from a scan; nothing is estimated.
# Exit 0 = scan completed (violations are DATA, not failure). Exit 2 = could not scan.
#
# The scanners live in lib/ and emit JSONL violations on stdout, one per line:
#   {"file":"..","line":N,"metric":"..","value":N,"cap":N,"severity":"..","name":".."}

set -uo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LIB="$HERE/lib"

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

ROOT="."
FORMAT="json"
EXCLUDE_EXTRA=""

usage() {
  cat <<'EOF'
caps.sh — measure file length, method length, nesting, loop bodies, else, params, public members.

  caps.sh [--root PATH] [--json|--text] [--exclude GLOB] [--help]

Caps are read from the environment so they are one place, not scattered:
  CG_CAP_FILE=250 CG_CAP_FILE_WARN=200
  CG_CAP_METHOD=25 CG_CAP_METHOD_WARN=15
  CG_CAP_NESTING=1 CG_CAP_LOOP_BODY=8
  CG_CAP_PARAMS=4 CG_CAP_PARAMS_WARN=3
  CG_CAP_PUBLIC=7 CG_CAP_PUBLIC_WARN=5

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
    --exclude) EXCLUDE_EXTRA="${2:?--exclude needs a glob}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'caps.sh: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[ -d "$ROOT" ] || { printf 'caps.sh: not a directory: %s\n' "$ROOT" >&2; exit 2; }
ROOT="$(cd -- "$ROOT" && pwd)"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/caps.XXXXXX")" || exit 2
trap 'rm -rf -- "$TMP"' EXIT
VIOL="$TMP/violations.jsonl"; : >"$VIOL"
DEGRADED="$TMP/degraded.txt"; : >"$DEGRADED"

# ---- file discovery: git when available (respects .gitignore), else find ----
PRUNE_DIRS='node_modules|\.git|dist|build|out|target|vendor|__pycache__|\.venv|venv|\.tox|\.next|coverage|\.mypy_cache|\.pytest_cache|migrations|generated|__generated__'
list_files() {
  if git -C "$ROOT" rev-parse --show-toplevel >/dev/null 2>&1; then
    git -C "$ROOT" ls-files -z | tr '\0' '\n' | sed "s|^|$ROOT/|"
  else
    find "$ROOT" -type f -print
  fi
}
list_files \
  | grep -Ev "/($PRUNE_DIRS)/" \
  | { [ -n "$EXCLUDE_EXTRA" ] && grep -v -- "$EXCLUDE_EXTRA" || cat; } \
  | grep -Ev '\.(min\.js|lock|map|snap|png|jpg|jpeg|gif|svg|pdf|zip|gz|ico|woff2?|ttf)$' \
  > "$TMP/all.txt"

pick() { grep -E "$1" "$TMP/all.txt" 2>/dev/null || true; }
pick '\.py$'                       > "$TMP/python.txt"
pick '\.(ts|tsx|js|jsx|mjs|cjs)$'  > "$TMP/ts.txt"
pick '\.(java|kt|kts)$'            > "$TMP/java.txt"
pick '\.go$'                       > "$TMP/go.txt"

# ---- file length applies to every text file, in every language ----
while IFS= read -r f; do
  [ -f "$f" ] || continue
  n=$(wc -l <"$f" | tr -d ' ')
  rel="${f#"$ROOT"/}"
  if [ "$n" -gt "$CAP_FILE" ]; then
    printf '{"file":"%s","line":1,"metric":"file_lines","value":%s,"cap":%s,"severity":"major","name":""}\n' \
      "$rel" "$n" "$CAP_FILE" >>"$VIOL"
  elif [ "$n" -gt "$CAP_FILE_WARN" ]; then
    printf '{"file":"%s","line":1,"metric":"file_lines","value":%s,"cap":%s,"severity":"minor","name":""}\n' \
      "$rel" "$n" "$CAP_FILE_WARN" >>"$VIOL"
  fi
done < <(file --mime-type -- $(tr '\n' ' ' <"$TMP/all.txt" 2>/dev/null) 2>/dev/null \
           | awk -F': ' '$2 ~ /^text\//{sub(/: [^:]*$/,"",$0); print $1}' 2>/dev/null \
         || cat "$TMP/all.txt")

# ---- python: exact, via the AST. No heuristic can match it, so prefer it hard. ----
FIDELITY="native"
if [ -s "$TMP/python.txt" ]; then
  if command -v python3 >/dev/null 2>&1 && [ -f "$LIB/scan_python.py" ]; then
    CG_CAP_METHOD="$CAP_METHOD" CG_CAP_METHOD_WARN="$CAP_METHOD_WARN" \
    CG_CAP_NESTING="$CAP_NESTING" CG_CAP_LOOP_BODY="$CAP_LOOP_BODY" \
    CG_CAP_PARAMS="$CAP_PARAMS" CG_CAP_PARAMS_WARN="$CAP_PARAMS_WARN" \
    CG_CAP_PUBLIC="$CAP_PUBLIC" CG_CAP_PUBLIC_WARN="$CAP_PUBLIC_WARN" \
    CG_ROOT="$ROOT" \
      python3 "$LIB/scan_python.py" <"$TMP/python.txt" >>"$VIOL" 2>"$TMP/py.err" \
      || { echo "python: scanner failed ($(tr -d '\n' <"$TMP/py.err" | tail -c 200))" >>"$DEGRADED"; FIDELITY="degraded"; }
  else
    echo "python: no python3 on PATH; python files counted for file length only" >>"$DEGRADED"
    FIDELITY="degraded"
  fi
fi

# ---- brace languages: one awk scanner, dialect passed in ----
scan_braces() {
  local list="$1" dialect="$2"
  [ -s "$list" ] || return 0
  if [ ! -f "$LIB/scan_braces.awk" ]; then
    echo "$dialect: lib/scan_braces.awk missing; file length only" >>"$DEGRADED"; FIDELITY="degraded"; return 0
  fi
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    awk -v FNAME="${f#"$ROOT"/}" -v DIALECT="$dialect" \
        -v CAP_METHOD="$CAP_METHOD" -v CAP_METHOD_WARN="$CAP_METHOD_WARN" \
        -v CAP_NESTING="$CAP_NESTING" -v CAP_LOOP_BODY="$CAP_LOOP_BODY" \
        -v CAP_PARAMS="$CAP_PARAMS" -v CAP_PARAMS_WARN="$CAP_PARAMS_WARN" \
        -f "$LIB/scan_braces.awk" "$f" >>"$VIOL" 2>/dev/null
  done <"$list"
}
scan_braces "$TMP/ts.txt"   "ts"
scan_braces "$TMP/java.txt" "java"
scan_braces "$TMP/go.txt"   "go"

# ---- other languages get file length only; say so rather than implying a clean scan ----
if [ -s "$TMP/all.txt" ]; then
  others=$(grep -Ev '\.(py|ts|tsx|js|jsx|mjs|cjs|java|kt|kts|go|md|json|ya?ml|toml|txt|cfg|ini|sql|html|css|scss)$' "$TMP/all.txt" | wc -l | tr -d ' ')
  [ "${others:-0}" -gt 0 ] && echo "$others files in unsupported languages: file length only" >>"$DEGRADED"
fi

# ---- aggregate. awk, so no jq dependency. ----
emit_json() {
  printf '{\n'
  printf '  "schema": "codegraph-caps/1",\n'
  printf '  "root": "%s",\n' "$ROOT"
  printf '  "fidelity": "%s",\n' "$FIDELITY"
  printf '  "caps": {"file_lines": %s, "file_lines_warn": %s, "method_lines": %s, "method_lines_warn": %s, "nesting": %s, "loop_body": %s, "params": %s, "params_warn": %s, "public_members": %s, "public_members_warn": %s},\n' \
    "$CAP_FILE" "$CAP_FILE_WARN" "$CAP_METHOD" "$CAP_METHOD_WARN" "$CAP_NESTING" \
    "$CAP_LOOP_BODY" "$CAP_PARAMS" "$CAP_PARAMS_WARN" "$CAP_PUBLIC" "$CAP_PUBLIC_WARN"
  printf '  "scanned": {"total": %s, "python": %s, "ts": %s, "java_kotlin": %s, "go": %s},\n' \
    "$(wc -l <"$TMP/all.txt" | tr -d ' ')" "$(wc -l <"$TMP/python.txt" | tr -d ' ')" \
    "$(wc -l <"$TMP/ts.txt" | tr -d ' ')" "$(wc -l <"$TMP/java.txt" | tr -d ' ')" \
    "$(wc -l <"$TMP/go.txt" | tr -d ' ')"
  printf '  "totals": {'
  LC_ALL=C sort "$VIOL" -o "$VIOL" 2>/dev/null || true
  awk '
    match($0, /"metric":"[^"]+"/)   { m = substr($0, RSTART+10, RLENGTH-11) }
    match($0, /"severity":"[^"]+"/) { s = substr($0, RSTART+12, RLENGTH-13) }
    { c[m "_" s]++; keys[m "_" s] = 1; worst[m] = (worst[m] > 0 ? worst[m] : 0) }
    match($0, /"value":[0-9]+/)     { v = substr($0, RSTART+8, RLENGTH-8) + 0
                                      if (v > worst[m]) worst[m] = v }
    END { n = 0
          for (k in keys) { printf "%s\"%s\": %d", (n++ ? ", " : ""), k, c[k] }
          for (k in worst) { printf "%s\"worst_%s\": %d", (n++ ? ", " : ""), k, worst[k] }
        }' "$VIOL"
  printf '},\n'
  printf '  "degraded": ['
  awk '{ gsub(/"/, "\\\""); printf "%s\"%s\"", (NR>1 ? ", " : ""), $0 }' "$DEGRADED"
  printf '],\n'
  printf '  "violations": [\n'
  awk '{ printf "%s    %s", (NR>1 ? ",\n" : ""), $0 } END { if (NR) printf "\n" }' "$VIOL"
  printf '  ]\n}\n'
}

emit_text() {
  printf 'caps.sh %s  (fidelity: %s)\n\n' "$ROOT" "$FIDELITY"
  awk 'match($0,/"metric":"[^"]+"/){m=substr($0,RSTART+10,RLENGTH-11)}
       match($0,/"severity":"[^"]+"/){s=substr($0,RSTART+12,RLENGTH-13)}
       {c[m" ("s")"]++} END{for(k in c) printf "%6d  %s\n", c[k], k}' "$VIOL" | LC_ALL=C sort -rn
  printf '\nworst 20:\n'
  LC_ALL=C sort -t: -k1,1 "$VIOL" | awk '
    match($0,/"file":"[^"]*"/){f=substr($0,RSTART+8,RLENGTH-9)}
    match($0,/"line":[0-9]+/){l=substr($0,RSTART+7,RLENGTH-7)}
    match($0,/"metric":"[^"]+"/){m=substr($0,RSTART+10,RLENGTH-11)}
    match($0,/"value":[0-9]+/){v=substr($0,RSTART+8,RLENGTH-8)}
    {printf "%6d  %-18s %s:%s\n", v, m, f, l}' | LC_ALL=C sort -rn | head -20
  [ -s "$DEGRADED" ] && { printf '\ndegraded:\n'; sed 's/^/  - /' "$DEGRADED"; }
  return 0
}

case "$FORMAT" in
  json) emit_json ;;
  text) emit_text ;;
esac
exit 0
