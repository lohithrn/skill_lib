#!/usr/bin/env bash
# graph.sh — build the module dependency graph. Router only: one extractor per language family.
#
# Emits `graph.json` (specs/graph-report.md §1) on stdout. Exit 0 = graph built, violations are
# DATA. Exit 2 = could not build a graph at all.
#
# Fidelity is reported, never assumed. Python goes through the AST and Go through `go list` when
# the toolchain is present; TypeScript and Java are a lexical import sweep. A lexical graph may
# NOT be used to claim "0 cycles" — jobs/analyze.md phase 1b requires the degradation in the
# verdict line, because an import the scanner could not see is a cycle nobody reports.

set -uo pipefail

# lib/ imports itself, so python would drop `__pycache__/` into the installed skill directory — a
# measurement tool that writes to the tree it was copied into. Nothing here is hot enough to care.
export PYTHONDONTWRITEBYTECODE=1

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LIB="$HERE/lib"

ROOT="."
FORMAT="json"
EXCLUDE_EXTRA=""
CYCLES_ONLY=0

usage() {
  cat <<'EOF'
graph.sh — module graph, cycles (Tarjan), fan-in/out, I/A/D, PageRank, propagation cost.

  graph.sh [--root PATH] [--json|--text] [--cycles] [--exclude REGEX] [--help]

  --json    full graph.json on stdout (default)
  --text    the four views a human reads: cycles, illegal edges, top centrality, port health
  --cycles  the cycle slice only, still honouring --json/--text. Same measurement, projected:
            for the refine loop, which asks "did this slice remove the cycle?" and should not be
            handed the whole graph to answer it. Carries `degraded` through, because an empty
            cycle list from a lexical scan is not a proof of acyclicity.

A cycle is DATA, not an error: exit stays 0 and the caller asserts on `totals.cycles`.

Languages: python (AST, exact), go (`go list` when the toolchain is present, else lexical),
typescript/javascript and java/kotlin (lexical import sweep). Anything else is not a node.

Every metric that cannot be computed within budget is OMITTED and the reason appears in
"degraded" — never zeroed. Cycles are reported exactly; the suggested cut edge is a candidate,
not a minimum feedback arc set (that problem is NP-hard).
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?--root needs a path}"; shift 2 ;;
    --json) FORMAT="json"; shift ;;
    --text) FORMAT="text"; shift ;;
    --cycles) CYCLES_ONLY=1; shift ;;
    --exclude) EXCLUDE_EXTRA="${2:?--exclude needs a regex}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'graph.sh: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[ -d "$ROOT" ] || { printf 'graph.sh: not a directory: %s\n' "$ROOT" >&2; exit 2; }
ROOT="$(cd -- "$ROOT" && pwd)"

# An unparseable --exclude makes `grep` exit non-zero, and the `|| cat` fallback below would then
# pass the UNFILTERED list through: the caller asked to skip a directory and got a graph that
# silently includes it. Refusing is the only honest answer. Same guard as caps.sh.
if [ -n "$EXCLUDE_EXTRA" ]; then
  printf '' | grep -q -- "$EXCLUDE_EXTRA" 2>/dev/null
  [ $? -le 1 ] || { printf 'graph.sh: --exclude is not a valid regex: %s\n' "$EXCLUDE_EXTRA" >&2; exit 2; }
fi
command -v python3 >/dev/null 2>&1 || {
  printf 'graph.sh: python3 is required to build the graph\n' >&2; exit 2; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/graph.XXXXXX")" || exit 2
trap 'rm -rf -- "$TMP"' EXIT
SCAN="$TMP/scan.jsonl"; : >"$SCAN"
NOTES="$TMP/notes.txt"; : >"$NOTES"

# ---- file discovery: git when available (respects .gitignore), else find ----
PRUNE_DIRS='node_modules|\.git|dist|build|out|target|vendor|__pycache__|\.venv|venv|\.tox|\.next|coverage|\.mypy_cache|\.pytest_cache|migrations|generated|__generated__'
# git is preferred because it applies .gitignore for free. `--others --exclude-standard` is not
# optional: plain `ls-files` lists only TRACKED files, so a module written but not yet committed
# would be invisible and the report would call the repo clean. "No files scanned" and "no cycles"
# must never produce the same output. `find` is the last resort and is announced, since without
# git the ignore rules are not applied and build output can enter the graph.
NL='
'

# We are pointed at code we did not write, so `git` runs with the analysed repo's own configuration
# DISABLED. `core.fsmonitor` is a config key whose value git EXECUTES, and a repo can ship one in
# `.git/config` — so `git clone <hostile> && graph.sh` would run the author's command as us before
# a line of source is read. A command-line `-c` outranks every config file, which also covers the
# same key arriving indirectly via `include.path`.
git_safe() {
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  GIT_TERMINAL_PROMPT=0 \
  git -C "$ROOT" --no-optional-locks \
      -c core.fsmonitor=false -c core.hooksPath=/dev/null \
      -c core.pager=cat -c core.editor=false \
      -c protocol.ext.allow=never -c uploadpack.packObjectsHook= \
      "$@"
}

# A newline in a filename would split one path into two list entries, and the fragment — being
# relative — resolves against the CALLER's directory, so the scanner would read a file outside the
# analysed tree and attribute the result to this repo. Refuse it and say so. Symlinks are skipped
# for the same reason: a committed `src/leak.py -> /etc/passwd` is an out-of-tree read.
skipped_unsafe=0
skipped_big=0
MAX_BYTES="${CG_MAX_FILE_BYTES:-5242880}"
emit_path() {
  local abs="$1"
  case "$abs" in *"$NL"*) skipped_unsafe=$((skipped_unsafe + 1)); return 0 ;; esac
  [ -L "$abs" ] && return 0
  [ -f "$abs" ] || return 0
  if [ "$MAX_BYTES" -gt 0 ]; then
    local sz
    sz=$(wc -c <"$abs" 2>/dev/null | tr -d ' ')
    if [ "${sz:-0}" -gt "$MAX_BYTES" ]; then skipped_big=$((skipped_big + 1)); return 0; fi
  fi
  printf '%s\n' "$abs"
}

# Why we fell back to `find`. Two DIFFERENT facts, and printing the wrong one puts a false
# statement in the report: a root that is no repository at all is not a repository that listed
# nothing. What both share — and what actually affects the graph — is that .gitignore went
# unapplied, so generated code can enter as nodes and invent edges.
fallback_reason() {
  [ "$1" -eq 1 ] && {
    printf 'git listed no files under this root; scanned the working tree instead, so .gitignore was not applied'
    return 0; }
  printf 'not a git repository; scanned the working tree, so .gitignore was not applied and generated code may appear as nodes'
}

list_files() {
  local used_git=0 in_repo=0
  git_safe rev-parse --show-toplevel >/dev/null 2>&1 && in_repo=1
  if [ "$in_repo" -eq 1 ]; then
    git_safe ls-files -z --cached --others --exclude-standard >"$TMP/list.z" 2>/dev/null \
      || : >"$TMP/list.z"
    [ -s "$TMP/list.z" ] && used_git=1
  fi
  if [ "$used_git" -eq 0 ]; then
    fallback_reason "$in_repo" >>"$NOTES"
    printf '\n' >>"$NOTES"
    find "$ROOT" -type f -print0 >"$TMP/list.z" 2>/dev/null || : >"$TMP/list.z"
  fi
  # NUL-delimited, so a filename containing a newline arrives as ONE entry and can be refused
  while IFS= read -r -d '' entry; do
    case "$entry" in
      /*) emit_path "$entry" ;;
      *)  emit_path "$ROOT/$entry" ;;
    esac
  done <"$TMP/list.z"
}
# NOT `list_files | grep ...`: the left side of a pipe is a subshell, and the skip counters
# incremented there would be discarded along with the caveats they produce.
list_files >"$TMP/raw.txt"
grep -Ev "/($PRUNE_DIRS)/" "$TMP/raw.txt" \
  | { [ -n "$EXCLUDE_EXTRA" ] && grep -v -- "$EXCLUDE_EXTRA" || cat; } \
  | grep -E '\.(py|ts|tsx|js|jsx|mjs|cjs|java|kt|kts|go)$' \
  | grep -Ev '\.min\.js$' \
  > "$TMP/src.txt"

[ "$skipped_unsafe" -gt 0 ] && \
  echo "$skipped_unsafe file(s) skipped: a newline in the filename cannot be carried safely; they are NOT in this graph" >>"$NOTES"
[ "$skipped_big" -gt 0 ] && \
  echo "$skipped_big file(s) over $MAX_BYTES bytes skipped (CG_MAX_FILE_BYTES); their imports are NOT in this graph" >>"$NOTES"

[ -s "$TMP/src.txt" ] || {
  printf 'graph.sh: no source files in a supported language under %s\n' "$ROOT" >&2; exit 2; }

# ---- go: a Go source import is ALREADY the full package path, so the lexical read of the
# import list is exact. What the source cannot tell us is the package's OWN import path — the
# module prefix lives in go.mod. `go list` supplies exactly that, as a dir -> import-path map,
# so targets match node ids directly instead of by suffix. This is the only thing go needs.
GO_NATIVE=0
GO_IDS="$TMP/go_ids.tsv"; : >"$GO_IDS"
map_go_ids() {
  grep -q '\.go$' "$TMP/src.txt" || return 0
  command -v go >/dev/null 2>&1 || {
    echo "go: no toolchain on PATH; package ids come from directory paths, not go.mod" >>"$NOTES"
    return 0; }
  [ -f "$ROOT/go.mod" ] || {
    echo "go: no go.mod at the root; package ids come from directory paths" >>"$NOTES"; return 0; }
  # `go list ./...` resolves modules, which on an ordinary repo whose deps are not in the local
  # module cache means a NETWORK fetch from proxy.golang.org — that alone would break the offline
  # guarantee. On a hostile repo it is worse: a `toolchain` line in go.mod makes the go command
  # download and EXECUTE a different toolchain, and a go.work redirects resolution. So: readonly
  # (never rewrite go.mod, never fetch), proxy off, toolchain pinned to the installed one, workspace
  # ignored. A failure here is already handled as a documented degradation, which is the point —
  # refusing to fetch turns a silent network call into a visible caveat.
  ( cd "$ROOT" && env GOFLAGS=-mod=readonly GOPROXY=off GONOSUMDB='*' GOSUMDB=off \
        GOTOOLCHAIN=local GOWORK=off GIT_TERMINAL_PROMPT=0 \
        go list -e -f '{{.Dir}}	{{.ImportPath}}' ./... ) \
    >"$GO_IDS" 2>"$TMP/go.err" || {
      echo "go: \`go list\` failed ($(tr -d '\n' <"$TMP/go.err" | tail -c 160)); using directory paths" >>"$NOTES"
      : >"$GO_IDS"; return 0; }
  [ -s "$GO_IDS" ] && GO_NATIVE=1
}
map_go_ids

# ---- one scanner for every file: python through the AST, the rest lexically ----
CG_ROOT="$ROOT" CG_GO_IDS="$GO_IDS" \
  python3 "$LIB/imports_scan.py" <"$TMP/src.txt" >>"$SCAN" 2>"$TMP/scan.err" || {
    printf 'graph.sh: import scan failed:\n' >&2; cat "$TMP/scan.err" >&2; exit 2; }
if [ -s "$TMP/scan.err" ]; then
  # Name the files in the note itself. "(see stderr)" pointed at a buffer this script captured
  # and then deleted on exit, so the reader was sent to output that no longer existed.
  gaveup=$(grep -c 'giving up' "$TMP/scan.err" 2>/dev/null || echo 0)
  which=$(grep 'giving up' "$TMP/scan.err" 2>/dev/null | sed 's/.*giving up[^A-Za-z0-9_./-]*//' \
          | head -5 | tr '\n' ' ')
  echo "scanner gave up on ${gaveup} file(s), so their imports are NOT in this graph: ${which:-unnamed}" >>"$NOTES"
fi

[ -s "$SCAN" ] || { printf 'graph.sh: nothing scanned\n' >&2; exit 2; }

# ---- fidelity notes: name the better tool when it exists rather than implying this is exact ----
if grep -q '"lang":"ts"' "$SCAN"; then
  echo "typescript/javascript read lexically: tsconfig path aliases beyond @/ are unresolved" >>"$NOTES"
  command -v depcruise >/dev/null 2>&1 \
    && echo "typescript: dependency-cruiser is installed and would be exact (needs tsPreCompilationDeps + tsConfig)" >>"$NOTES"
fi
grep -q '"lang":"java"' "$SCAN" \
  && echo "java/kotlin read lexically: wildcard imports and same-package references are not edges here" >>"$NOTES"

# ---- build ----
CG_ROOT="$ROOT" python3 "$LIB/graph_build.py" <"$SCAN" >"$TMP/graph.json" 2>"$TMP/build.err" || {
  printf 'graph.sh: graph build failed:\n' >&2; cat "$TMP/build.err" >&2; exit 2; }

# Fold the shell's own fidelity notes into the JSON's `degraded` list, so one artifact carries
# every caveat. A caveat that lives only in stderr is a caveat nobody reads.
CG_NOTES_FILE="$NOTES" CG_GO_NATIVE="$GO_NATIVE" \
  python3 "$LIB/graph_notes.py" <"$TMP/graph.json" >"$TMP/graph.final.json" || {
    printf 'graph.sh: could not annotate fidelity\n' >&2; exit 2; }

if [ "$CYCLES_ONLY" -eq 1 ]; then
  CG_CYCLES_FORMAT="$FORMAT" python3 "$LIB/graph_cycles.py" <"$TMP/graph.final.json" || exit 2
  exit 0
fi

case "$FORMAT" in
  json) cat "$TMP/graph.final.json" ;;
  text) python3 "$LIB/graph_render.py" <"$TMP/graph.final.json" ;;
esac
exit 0
