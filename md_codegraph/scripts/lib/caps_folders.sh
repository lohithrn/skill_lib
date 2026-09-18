#!/usr/bin/env bash
# caps_folders.sh — how many code files sit DIRECTLY in one folder. Sourced by caps.sh.
#
# Reads $TMP/code.txt (absolute paths), $ROOT, $VIOL, $CAP_FOLDER, $CAP_FOLDER_WARN.
#
# The only cap here whose subject is a DIRECTORY, because the doctrine's claim is about the tree:
# a folder is a question, a file is an answer (doctrine.md §9). Twenty answers in one folder means
# either the question was never asked or it is really several questions, and no reader can tell
# which from the tree. Subfolders are NEVER counted — depth is the fix, so capping it would punish
# the fix. A folder may hold any number of folders.

TAB="$(printf '\t')"

# Two extension groups are excluded from the COUNT, for reasons that are about the language and
# not about taste:
#   .tf/.tfvars — in Terraform the DIRECTORY is the module. Splitting a module's files into
#                 subfolders creates a different module, so the remedy this cap asks for does not
#                 exist there, and a cap whose remedy is illegal is a false finding.
#   .h/.hpp     — a header declares the answer its source defines; counting both doubles every
#                 C/C++ folder. A header-only library therefore undercounts: declared, not hidden.
FOLDER_SKIP_RE='\.(tf|tfvars|h|hpp)$'

# A directory has no declaration to hang a pragma above, so the folder-level exemption lives in a
# file of its own IN the folder it exempts: `.codegraph-exempt`, carrying the SAME grammar as the
# source pragma. Same two conditions — name the metric, carry a reason — and the breach is still
# printed with severity `exempt`, so the report says what it chose not to count.
#
#   codegraph:exempt folder_files -- 9 payment providers: one question, nine total answers
#
# `lib/cap_pragma.py` never sees this metric: a `folder_files` pragma in a source line suppresses
# nothing, because the thing it would have to exempt is not on that line.
#
# THREE outcomes, not two. A marker that names the metric and gives no reason is a different state
# from no marker at all: the author tried to exempt and wrote nothing citable, and silence there
# reads back to them as "it worked". `scan_python.py` already reports that case as its own
# `exempt_without_reason` major for a source pragma, so a folder marker gets the same record and the
# grammar is uniform wherever it is written.
#   0 = exempted, reason given · 2 = names the metric, no reason · 1 = not exempted here
folder_exempt() {
  local marker="$1/.codegraph-exempt"
  [ -f "$marker" ] && [ ! -L "$marker" ] || return 1
  grep -Eq 'codegraph:exempt[^-]*[[:space:],]folder_files([[:space:],][^-]*)?--[[:space:]]*[^[:space:]]' \
    "$marker" 2>/dev/null && return 0
  grep -Eq 'codegraph:exempt([[:space:],][^-]*)?[[:space:],]folder_files([[:space:],]|$)' \
    "$marker" 2>/dev/null && return 2
  return 1
}

folder_violation() {
  printf '{"file":"%s","line":1,"metric":"folder_files","value":%s,"cap":%s,"severity":"%s","name":""}\n' \
    "$1" "$2" "$3" "$4" >>"$VIOL"
}

# `name` carries the metric the reasonless marker tried to exempt, matching `scan_python.py`'s record
# for the source-pragma case, so one gate keyed on `exempt_without_reason_major` catches both.
folder_exempt_without_reason() {
  printf '{"file":"%s","line":1,"metric":"exempt_without_reason","value":1,"cap":0,"severity":"major","name":"folder_files"}\n' \
    "$1" >>"$VIOL"
}

# The folder is derived from the RELATIVE path, so the count is a property of the repo and not of
# where it happens to be checked out. `line` is 1 in every record because a directory has no line
# and every consumer renders `file:line`; the trailing `/` on the path is what says it is a folder.
#
# The prefix is built in SHELL and passed in, for two reasons that both silently break the relative
# derivation — and with it every folder exemption, since `folder_exempt` is handed `$ROOT/$dir`:
#   * `awk -v` escape-processes its value (see `caps.sh` scan_braces), so a checkout under
#     `/tmp/back\slash` reaches awk as `/tmp/backslash`, `index()` never matches, and every folder
#     path comes out ABSOLUTE — which the hostile-input suite forbids outright. Double the
#     backslashes and awk collapses them back.
#   * `--root /` would make the prefix `//`, which matches nothing. Append the separator only when
#     the root does not already end in one.
folder_root_prefix() {
  local p="$ROOT"
  [ "${p%/}" = "$p" ] && p="$p/"
  printf '%s' "${p//\\/\\\\}"
}

count_by_folder() {
  awk -v root="$(folder_root_prefix)" '
    { p = $0
      if (index(p, root) == 1) { p = substr(p, length(root) + 1) }
      n = split(p, seg, "/")
      d = "."
      if (n > 1) { d = seg[1]; for (i = 2; i < n; i++) { d = d "/" seg[i] } }
      c[d]++ }
    END { for (d in c) { printf "%d\t%s\n", c[d], d } }' "$TMP/folder_code.txt"
}

scan_folders() {
  : >"$TMP/folder_code.txt"
  : >"$TMP/folders.txt"
  [ -s "$TMP/code.txt" ] || return 0
  # `sort -u`, not just `sort`: during an unresolved merge `git ls-files` emits a conflicted path
  # ONCE PER INDEX STAGE, so a 5-file folder mid-merge counts as 15 and crosses the hard cap on
  # nothing but merge state. Every other metric reads one file at a time and only duplicates a
  # record; this one aggregates, so the duplication becomes a wrong NUMBER — and folder fan-out is
  # exactly what gets measured mid-restructure, which is when a merge is in flight.
  grep -Ev "$FOLDER_SKIP_RE" "$TMP/code.txt" | LC_ALL=C sort -u >"$TMP/folder_code.txt" || true
  [ -s "$TMP/folder_code.txt" ] || return 0
  count_by_folder | LC_ALL=C sort -t"$TAB" -k2 >"$TMP/folders.txt"
  local n dir abs ex
  while IFS="$TAB" read -r n dir; do
    [ "$n" -gt "$CAP_FOLDER_WARN" ] || continue
    abs="${ROOT%/}"
    [ "$dir" = "." ] || abs="${ROOT%/}/$dir"
    ex=0; folder_exempt "$abs" || ex=$?
    if [ "$ex" -eq 0 ]; then
      folder_violation "$(jstr "$dir/")" "$n" "$CAP_FOLDER" exempt
      continue
    fi
    # A reasonless marker suppresses nothing, so the breach below still gets its real severity; this
    # record is the extra one that tells the author their marker is not doing what they think.
    [ "$ex" -eq 2 ] && folder_exempt_without_reason "$(jstr "$dir/")"
    [ "$n" -gt "$CAP_FOLDER" ] && { folder_violation "$(jstr "$dir/")" "$n" "$CAP_FOLDER" major; continue; }
    folder_violation "$(jstr "$dir/")" "$n" "$CAP_FOLDER_WARN" minor
  done <"$TMP/folders.txt"
}
