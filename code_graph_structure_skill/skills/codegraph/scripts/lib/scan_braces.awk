# scan_braces.awk — cap measurement for brace languages: ts/js, java/kotlin, go.
#
# Emits JSONL violations. Invoked per file by caps.sh with:
#   -v FNAME=<repo-relative path> -v DIALECT=ts|java|go
#   -v CAP_METHOD -v CAP_METHOD_WARN -v CAP_NESTING -v CAP_LOOP_BODY -v CAP_PARAMS -v CAP_PARAMS_WARN
#
# Honest about its own accuracy: this is a lexical scan, not a parse. It strips strings and
# comments, then classifies each `{` by the text that precedes it. That is right for ordinary
# code and wrong for pathological code; a parser-backed count (tree-sitter, ts-morph, javaparser,
# go/ast) is strictly better and caps.sh should prefer one when the repo already has it.

function jesc(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); gsub(/\t/, " ", s); return s }

function emit(line, metric, value, cap, severity, name) {
  printf "{\"file\":\"%s\",\"line\":%d,\"metric\":\"%s\",\"value\":%d,\"cap\":%d,\"severity\":\"%s\",\"name\":\"%s\"}\n",
         jesc(FNAME), line, metric, value, cap, severity, jesc(name)
}

# awk has no local variables: every temp MUST be declared as a trailing parameter, or it
# clobbers the caller. The main scan loop uses `i` and `n`, so a helper that used them silently
# corrupted the character walk. Extra params below are locals, not arguments.

# Remove string/char/template literals and comments so braces and keywords are real code.
function sanitize(s,   rest) {
  if (inblock) {
    if (match(s, /\*\//)) { s = substr(s, RSTART + 2); inblock = 0 } else { return "" }
  }
  gsub(/\\./, "..", s)                                  # escapes first, so \" cannot close
  gsub(/"[^"]*"/, "\"\"", s)
  gsub(/'[^']*'/, "''", s)
  gsub(/`[^`]*`/, "``", s)
  if (match(s, /\/\*/)) {
    rest = substr(s, RSTART)
    if (match(rest, /\*\//)) { sub(/\/\*.*\*\//, " ", s) } else { s = substr(s, 1, RSTART - 1); inblock = 1 }
  }
  sub(/\/\/.*$/, "", s)
  if (DIALECT == "go") sub(/#.*$/, "", s)               # build pragmas only; harmless elsewhere
  return s
}

# Count top-level commas in a parameter list, ignoring nested (), [], <>, {}.
function count_params(sig,   body, d, np, seen, ci, c) {
  if (!match(sig, /\(/)) return 0
  body = substr(sig, RSTART + 1); d = 0; np = 0; seen = 0
  for (ci = 1; ci <= length(body); ci++) {
    c = substr(body, ci, 1)
    if (c == "(" || c == "[" || c == "<" || c == "{") d++
    else if (c == ")" && d == 0) break
    else if (c == ")" || c == "]" || c == ">" || c == "}") d--
    else if (c == "," && d == 0) np++
    else if (c != " " && c != "\t") seen = 1
  }
  return seen ? np + 1 : 0
}

function is_control(h) { return h ~ /(^|[^A-Za-z0-9_$])(if|else|switch|catch|try|finally|when|select)([^A-Za-z0-9_$]|$)/ }
function is_loop(h)    { return h ~ /(^|[^A-Za-z0-9_$])(for|while|do)([^A-Za-z0-9_$]|$)/ ||
                                h ~ /\.(forEach|map|filter|reduce|flatMap)[ \t]*\(/ }
function is_type(h)    { return h ~ /(^|[^A-Za-z0-9_$])(class|interface|struct|enum|object|namespace|trait|impl)([^A-Za-z0-9_$]|$)/ }

# Does this header declare a function? Dialect-specific, because the shapes differ genuinely.
function is_func(h) {
  if (is_control(h) || is_loop(h) || is_type(h)) return 0
  if (DIALECT == "go")   return h ~ /(^|[^A-Za-z0-9_])func([^A-Za-z0-9_]|[ \t]*\()/
  if (DIALECT == "java") return h ~ /\)[ \t]*(throws[ A-Za-z0-9_,.<>]*)?(:[^={]*)?[ \t]*$/ &&
                                h ~ /[A-Za-z0-9_>\]][ \t]*\(/
  return h ~ /(^|[^A-Za-z0-9_$])(function|fun)([^A-Za-z0-9_$]|[ \t]*\()/ ||
         h ~ /=>[ \t]*$/ ||
         (h ~ /^[ \t]*(export[ \t]+)?(public|private|protected|internal|static|async|override|readonly|get|set|\*)?[ \t]*[A-Za-z_$][A-Za-z0-9_$]*[ \t]*(<[^(]*>)?[ \t]*\(/ && h ~ /\)[ \t]*(:[^={]*)?[ \t]*$/)
}

function type_name(h,   t) {
  t = h
  if (match(t, /(class|interface|struct|enum|object|namespace|trait)[ \t]+[A-Za-z_$][A-Za-z0-9_$]*/)) {
    t = substr(t, RSTART, RLENGTH); sub(/^[a-z]+[ \t]+/, "", t); return t
  }
  return "(anonymous)"
}

function func_name(h,   t) {
  t = h
  if (DIALECT == "go") { if (match(t, /func[ \t]+(\([^)]*\)[ \t]*)?[A-Za-z0-9_]+/)) {
                           t = substr(t, RSTART, RLENGTH); sub(/^func[ \t]+(\([^)]*\)[ \t]*)?/, "", t); return t } }
  if (match(t, /[A-Za-z_$][A-Za-z0-9_$]*[ \t]*\(/)) { t = substr(t, RSTART, RLENGTH); sub(/[ \t]*\($/, "", t); return t }
  return "(anonymous)"
}

BEGIN { depth = 0; funcdepth = -1; ctrl = 0; maxctrl = 0; inblock = 0; typedepth = -1; pub = 0 }

{
  s = sanitize($0)
  # `hs` accumulates the sanitized text since the last `{`, `}` or `;` — that is the "header"
  # that classifies the next brace. It carries across lines so a multi-line signature still
  # classifies as a function. It must START from the carry, not from the whole current line.
  hs = header_carry

  # Walk characters so a line that both opens and closes is handled correctly.
  for (i = 1; i <= length(s); i++) {
    c = substr(s, i, 1)

    if (c == "{") {
      depth++
      k = "other"
      if      (is_func(hs))    k = "func"
      else if (is_loop(hs))    k = "loop"
      else if (is_control(hs)) k = "ctrl"
      else if (is_type(hs))    k = "type"
      kind[depth] = k; startln[depth] = NR

      if (k == "func" && funcdepth < 0) {
        funcdepth = depth; ctrl = 0; maxctrl = 0; fname = func_name(hs); fline = NR
        p = count_params(hs)
        if (p > CAP_PARAMS)           emit(NR, "params", p, CAP_PARAMS, "major", fname)
        else if (p > CAP_PARAMS_WARN) emit(NR, "params", p, CAP_PARAMS_WARN, "minor", fname)
      }
      else if (funcdepth >= 0 && (k == "ctrl" || k == "loop")) {
        ctrl++
        # Record the peak and report it once, at function close. Reporting every level as it
        # opens turns one over-nested method into four findings pointing at the same problem.
        if (ctrl > maxctrl) { maxctrl = ctrl; maxctrl_line = NR }
      }
      if (k == "type") { typedepth = depth; pub = 0; tname = type_name(hs) }
      hs = ""
      continue
    }

    if (c == "}") {
      if (depth > 0) {
        k = kind[depth]; st = startln[depth]
        if (k == "loop") {
          n = NR - st                                # body lines between the braces
          if (n > CAP_LOOP_BODY) emit(st, "loop_body", n, CAP_LOOP_BODY, "major", fname)
        }
        if (k == "ctrl" || k == "loop") { if (funcdepth >= 0 && ctrl > 0) ctrl-- }
        if (depth == funcdepth) {
          n = NR - st - 1                            # exclude the brace lines themselves
          if (n < 0) n = 0
          if (n > CAP_METHOD)           emit(fline, "method_lines", n, CAP_METHOD, "major", fname)
          else if (n > CAP_METHOD_WARN) emit(fline, "method_lines", n, CAP_METHOD_WARN, "minor", fname)
          if (maxctrl > CAP_NESTING)    emit(maxctrl_line, "nesting", maxctrl, CAP_NESTING, "major", fname)
          funcdepth = -1; ctrl = 0; maxctrl = 0
        }
        if (depth == typedepth) {
          if (pub > CAP_PUBLIC)           emit(st, "public_members", pub, CAP_PUBLIC, "major", tname)
          else if (pub > CAP_PUBLIC_WARN) emit(st, "public_members", pub, CAP_PUBLIC_WARN, "minor", tname)
          typedepth = -1; pub = 0
        }
        delete kind[depth]; delete startln[depth]
        depth--
      }
      hs = ""
      continue
    }

    # A `;` normally ends a statement and resets the header. But Go's `for a; b; c {` and
    # C-style `for (a; b; c)` carry the keyword across semicolons — dropping it there would
    # misclassify every counted loop as a plain block, so keep a header that already decided.
    if (c == ";") { if (!is_loop(hs) && !is_control(hs)) hs = ""; continue }
    hs = hs c
  }

  # `else` is a finding wherever it appears, including gofmt's `} else {`.
  if (s ~ /(^|[^A-Za-z0-9_$])else([^A-Za-z0-9_$]|$)/) {
    kindw = (s ~ /else[ \t]+if/) ? "else if" : "else"
    emit(NR, "else", 1, 0, "major", fname " (" kindw ")")
  }
  # Public member tally for the enclosing type. Java/Kotlin/TS mark it; Go capitalises it.
  if (typedepth >= 0 && depth == typedepth) {
    if (DIALECT == "go") { if (s ~ /^[ \t]*[A-Z][A-Za-z0-9_]*[ \t]+/) pub++ }
    else if (s ~ /^[ \t]*(public|export)[ \t]/) pub++
    else if (DIALECT == "ts" && s ~ /^[ \t]*[A-Za-z_$][A-Za-z0-9_$]*[ \t]*(<[^(]*>)?[ \t]*\(/ &&
             s !~ /^[ \t]*(private|protected|constructor)/) pub++
  }

  # Carry an unterminated header to the next line so a multi-line signature still classifies.
  # Bounded: a "header" longer than 400 chars is not a signature, it is drift — reset.
  header_carry = (hs != "" && length(hs) < 400) ? hs " " : ""
}

END {
  # An unbalanced file means the scan drifted; say so rather than reporting confident numbers.
  if (depth != 0) emit(NR, "unbalanced_braces", depth, 0, "minor", "scan fidelity degraded for this file")
}
