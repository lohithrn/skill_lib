# graph_files.sh — decide WHICH files the graph is built from, and declare what was left out.
#
# Sourced by graph.sh, never executed: `list_files | grep ...` would put the loop in a subshell and
# the skip counters incremented there — along with every caveat they produce — would be discarded
# at the closing pipe. Expects $ROOT, $TMP, $NOTES, $PRUNE_DIRS, $EXCLUDE_EXTRA and git_safe.
#
# Separate from graph.sh because "which files exist" and "what do they import" are two questions
# with two reasons to change, and the answer to the first one is where the safety rules live.

# A newline in a filename would split one path into two list entries, and the fragment — being
# relative — resolves against the CALLER's directory, so the scanner would read a file outside the
# analysed tree and attribute the result to this repo. Refuse it and say so. Symlinks are skipped
# for the same reason: a committed `src/leak.py -> /etc/passwd` is an out-of-tree read. Every C0
# control character is refused, not just the newline: a raw CR would ride into the JSON and make
# the whole document unparseable at exit 0 — one `touch` denying the run.
skipped_unsafe=0
skipped_big=0

# One outlier — a vendored bundle, a generated client — otherwise dominates every count and lets
# the repo hide behind it. Skip it, name it in `degraded`, keep measuring everything else.
MAX_BYTES="${CG_MAX_FILE_BYTES:-5242880}"

emit_path() {
  local abs="$1"
  case "$abs" in *[[:cntrl:]]*) skipped_unsafe=$((skipped_unsafe + 1)); return 0 ;; esac
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

# Writes $TMP/src.txt and appends one note per class of refusal. Every refusal is declared:
# skipped-and-declared beats scanned-wrong, but skipped-and-silent overstates coverage.
collect_sources() {
  list_files >"$TMP/raw.txt"
  grep -Ev "/($PRUNE_DIRS)/" "$TMP/raw.txt" \
    | { [ -n "$EXCLUDE_EXTRA" ] && grep -v -- "$EXCLUDE_EXTRA" || cat; } \
    | grep -E '\.(py|ts|tsx|js|jsx|mjs|cjs|java|kt|kts|go)$' \
    | grep -Ev '\.min\.js$' \
    > "$TMP/src.txt"
  [ "$skipped_unsafe" -gt 0 ] && \
    echo "$skipped_unsafe file(s) skipped: a newline or control character in the filename cannot be carried safely; they are NOT in this graph" >>"$NOTES"
  [ "$skipped_big" -gt 0 ] && \
    echo "$skipped_big file(s) over $MAX_BYTES bytes skipped (CG_MAX_FILE_BYTES); their imports are NOT in this graph" >>"$NOTES"
  return 0
}
