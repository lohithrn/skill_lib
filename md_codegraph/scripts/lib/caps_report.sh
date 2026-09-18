#!/usr/bin/env bash
# caps_report.sh — how a completed scan is SAID. Sourced by caps.sh, never executed.
#
# Two views over one file of JSONL violations, and no measurement: nothing here may compute a
# number that is not already in `$VIOL`. That is the point of the split — a bug in a renderer can
# make the report unreadable, but it cannot make the report wrong.
#
# awk throughout, so the skill has no jq dependency and runs on a bare machine.

emit_json() {
  printf '{\n'
  printf '  "schema": "codegraph-caps/1",\n'
  printf '  "root": "%s",\n' "$(jstr "$ROOT")"
  printf '  "fidelity": "%s",\n' "$FIDELITY"
  printf '  "caps": {"file_lines": %s, "file_lines_warn": %s, "folder_files": %s, "folder_files_warn": %s, "method_lines": %s, "method_lines_warn": %s, "nesting": %s, "loop_body": %s, "params": %s, "params_warn": %s, "public_members": %s, "public_members_warn": %s},\n' \
    "$CAP_FILE" "$CAP_FILE_WARN" "$CAP_FOLDER" "$CAP_FOLDER_WARN" "$CAP_METHOD" "$CAP_METHOD_WARN" "$CAP_NESTING" \
    "$CAP_LOOP_BODY" "$CAP_PARAMS" "$CAP_PARAMS_WARN" "$CAP_PUBLIC" "$CAP_PUBLIC_WARN"
  # `folders` is how many folders hold code at all, so a reader can see a "4 folders over the cap"
  # total against 6 folders total and read it as a flat repo rather than four local problems.
  printf '  "scanned": {"total": %s, "code": %s, "folders": %s, "python": %s, "ts": %s, "java_kotlin": %s, "go": %s},\n' \
    "$(wc -l <"$TMP/all.txt" | tr -d ' ')" "$(wc -l <"$TMP/code.txt" | tr -d ' ')" \
    "$(wc -l <"$TMP/folders.txt" | tr -d ' ')" \
    "$(wc -l <"$TMP/python.txt" | tr -d ' ')" \
    "$(wc -l <"$TMP/ts.txt" | tr -d ' ')" "$(wc -l <"$TMP/java.txt" | tr -d ' ')" \
    "$(wc -l <"$TMP/go.txt" | tr -d ' ')"
  printf '  "totals": {'
  LC_ALL=C sort "$VIOL" -o "$VIOL" 2>/dev/null || true
  count_totals
  printf '},\n'
  printf '  "degraded": ['
  awk '{ gsub(/"/, "\\\""); printf "%s\"%s\"", (NR>1 ? ", " : ""), $0 }' "$DEGRADED"
  printf '],\n'
  printf '  "violations": [\n'
  awk '{ printf "%s    %s", (NR>1 ? ",\n" : ""), $0 } END { if (NR) printf "\n" }' "$VIOL"
  printf '  ]\n}\n'
}

# One count per metric+severity pair, plus the worst value seen per metric. `worst_*` is what makes
# a total actionable: "11 method_lines_minor" says how many, "worst_method_lines: 44" says whether
# the next slice is a rename or a rewrite.
count_totals() {
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

# The format is DATA: the view's name IS the key, resolved to a function by name rather than
# selected by a branch, so a third view is a new `emit_<name>` function and no edit here. An
# unknown name falls back to the artifact, never to the pretty view — a caller that planned to
# parse this must not silently receive prose.
render() {
  local view="emit_$1"
  declare -f "$view" >/dev/null 2>&1 || view="emit_json"
  "$view"
}
