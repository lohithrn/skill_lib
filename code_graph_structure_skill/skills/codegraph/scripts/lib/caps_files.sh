#!/usr/bin/env bash
# caps_files.sh — which files may be measured, and how a path is carried without being trusted.
#
# SOURCED by caps.sh, never executed. It defines functions and two counters; `$ROOT` and `$TMP` are
# read at CALL time, so the caller may set them after sourcing.
#
# This file is the trust boundary of the whole script, and that is why it is a file of its own:
# caps.sh is pointed at code we did not write, so every rule here exists to stop that code from
# choosing what runs or what gets reported. Nothing in here measures anything.

# ---- file discovery: git when available (respects .gitignore), else find ----
PRUNE_DIRS='node_modules|\.git|dist|build|out|target|vendor|__pycache__|\.venv|venv|\.tox|\.next|coverage|\.mypy_cache|\.pytest_cache|migrations|generated|__generated__'
NL='
'

# One planted 200 MB source file is enough to OOM a scanner, and a failed scanner drops a whole
# LANGUAGE to file-length-only — which would let every method-length and nesting breach in the
# repo hide behind it. Skip the outlier, name it in `degraded`, keep measuring everything else.
MAX_BYTES="${CG_MAX_FILE_BYTES:-5242880}"

# JSON string escape for values that come from the filesystem. A quote or a backslash in a
# filename would otherwise emit a broken record, and a broken record fails the consumer's parse
# for the whole run — a hostile repo could deny the entire analysis with one `mkdir`.
jstr() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//	/\\t}"
  printf '%s' "$s"
}

# We are pointed at code we did not write, so `git` is invoked with the analysed repo's own
# configuration DISABLED. `core.fsmonitor` is a config key whose value git EXECUTES; a repo can
# ship one in `.git/config`, so `git clone <hostile> && caps.sh` would run the author's command
# as us before a line of source is read. A command-line `-c` outranks every config file, which
# also covers the same key arriving indirectly through `include.path`.
git_safe() {
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_NOSYSTEM=1 \
  GIT_TERMINAL_PROMPT=0 \
  git -C "$ROOT" --no-optional-locks \
      -c core.fsmonitor=false -c core.hooksPath=/dev/null \
      -c core.pager=cat -c core.editor=false \
      -c protocol.ext.allow=never -c uploadpack.packObjectsHook= \
      "$@"
}

# Emit one absolute path per line, and refuse the paths that cannot be carried safely on a line.
# A newline in a filename would otherwise split into two list entries, and the fragment — being
# relative — would resolve against the CALLER's directory, so the tool would read a file outside
# the tree it was asked about and report it as a finding of this repo. Skipped-and-declared beats
# scanned-wrong: every refusal lands in `degraded`, so coverage is never overstated.
#
# The refusal covers EVERY C0 control character, not just the newline: `jstr` escapes `\`, `"` and
# TAB, so a bare CR or ESC in a filename would travel into the JSON as a raw control byte and make
# the whole document unparseable while the script still exits 0 — one `touch` denying every run.
skipped_unsafe=0
skipped_big=0
emit_path() {
  local abs="$1"
  case "$abs" in *[[:cntrl:]]*) skipped_unsafe=$((skipped_unsafe + 1)); return 0 ;; esac
  [ -L "$abs" ] && return 0          # a symlink can point anywhere; -type f already skips these
  [ -f "$abs" ] || return 0
  if [ "$MAX_BYTES" -gt 0 ]; then
    local sz
    sz=$(wc -c <"$abs" 2>/dev/null | tr -d ' ')
    if [ "${sz:-0}" -gt "$MAX_BYTES" ]; then skipped_big=$((skipped_big + 1)); return 0; fi
  fi
  printf '%s\n' "$abs"
}

# Why we fell back to `find`. Two DIFFERENT facts, and printing the wrong one puts a false statement
# in the report: a root that is no repository at all is not a repository that listed nothing. What
# both share is that .gitignore went unapplied, so generated files can be measured as if they were
# authored — and a 300-line generated file is a finding nobody can act on.
fallback_reason() {
  [ "$1" -eq 1 ] && {
    printf 'git listed no files under this root; measured the working tree instead, so .gitignore was not applied'
    return 0; }
  printf 'not a git repository; measured the working tree, so .gitignore was not applied and generated files may be counted'
}

list_files() {
  local used_git=0 in_repo=0
  git_safe rev-parse --show-toplevel >/dev/null 2>&1 && in_repo=1
  if [ "$in_repo" -eq 1 ]; then
    # --others --exclude-standard is not optional: plain `ls-files` lists TRACKED files only, so a
    # scan of work in progress would silently skip every new file and still report fidelity=native.
    # --exclude-standard keeps .gitignore honoured, which is the only reason to prefer git here.
    git_safe ls-files -z --cached --others --exclude-standard >"$TMP/list.z" 2>/dev/null || : >"$TMP/list.z"
    [ -s "$TMP/list.z" ] && used_git=1
  fi
  if [ "$used_git" -eq 0 ]; then
    # Announced, exactly as graph.sh does. caps.sh used to fall back in silence, which reported
    # `fidelity: native` over a file list that .gitignore never filtered.
    fallback_reason "$in_repo" >>"$DEGRADED"
    printf '\n' >>"$DEGRADED"
    find "$ROOT" -type f -print0 >"$TMP/list.z" 2>/dev/null || : >"$TMP/list.z"
  fi
  # NUL-delimited read, so a filename containing a newline arrives as ONE entry and can be refused
  while IFS= read -r -d '' entry; do
    case "$entry" in
      /*) emit_path "$entry" ;;
      *)  emit_path "$ROOT/$entry" ;;
    esac
  done <"$TMP/list.z"
}

# Write the refusals into $DEGRADED and print the word to force `fidelity` to — or nothing at all
# when there was no refusal. Printed ONCE however many counters fired, because the caller
# substitutes this into a field and two caveats must not produce the value "degradeddegraded".
skip_notes() {
  local forced=""
  if [ "$skipped_unsafe" -gt 0 ]; then
    echo "$skipped_unsafe file(s) skipped: a newline or control character in the filename cannot be carried safely" >>"$DEGRADED"
    forced="degraded"
  fi
  if [ "$skipped_big" -gt 0 ]; then
    echo "$skipped_big file(s) over $MAX_BYTES bytes skipped (CG_MAX_FILE_BYTES); not measured" >>"$DEGRADED"
    forced="degraded"
  fi
  printf '%s' "$forced"
}
