#!/usr/bin/env bash
#
# tests/smoke.sh — the invariants this repo must never lose.
#
#   bash tests/smoke.sh            run everything
#   bash tests/smoke.sh --list     list the checks
#
# Five groups:
#   OFFLINE  — no skill may reach the network at run time
#   SECURITY — no secrets, no banned auth material, no unsafe shell
#   WIRING   — every file a manifest or index promises must exist, and every documented key,
#              flag and `${CLAUDE_*}` path is one the tools really accept
#   BEHAVIOR — the measurement scripts produce correct numbers on a known fixture
#   HOSTILE  — a filename, a symlink or the analysed repo's own git config cannot inject,
#              execute, or read outside the tree
#
# Exit 0 = all pass. Exit 1 = a check failed. Exit 2 = the harness itself broke.

set -uo pipefail
IFS=$'\n\t'

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
# The layout is flat: every skill is a TOP-LEVEL `md_<name>/` directory holding SKILL.md. The
# `md_` prefix is the discovery contract, not decoration — it is what keeps `tests/` (and any
# future tooling directory) from being enumerated as a skill by a bare `./*/` glob.
SKILL_DIRS=$(cd "$ROOT" && ls -d ./md_*/ 2>/dev/null || true)
PASS=0
FAIL=0
FIXTURE=""

pass() { printf 'PASS  %s\n' "$*"; PASS=$((PASS + 1)); }
fail() { printf 'FAIL  %s\n' "$*"; FAIL=$((FAIL + 1)); }
info() { printf '      %s\n' "$*"; }
head2() { printf '\n== %s ==\n' "$*"; }

cleanup() { [ -n "$FIXTURE" ] && rm -rf -- "$FIXTURE"; }
trap cleanup EXIT

if [ "${1:-}" = "--list" ]; then
  grep -n '^check_' "${BASH_SOURCE[0]}" | sed 's/() {.*//; s/^/  /'
  exit 0
fi

command -v python3 >/dev/null 2>&1 || { echo "harness needs python3" >&2; exit 2; }

# ---------------------------------------------------------------- OFFLINE ----

check_no_network_in_skills() {
  # install.sh is allowed to clone. Reference docs may cite URLs as citations.
  # Executable skill content may not reach the network at all.
  local hits
  hits=$(cd "$ROOT" && grep -rn -E '(^|[^A-Za-z_])(curl|wget|nc|netcat)[[:space:]]|https?://|urllib|requests\.(get|post)|http\.client|socket\.|fetch\(|/dev/tcp|pip install|npm install|apt-get|brew install' \
        ./md_*/scripts/ ./md_*/agents/ 2>/dev/null | grep -v -E '\.md:[0-9]+:.*(cite|source|see |RFC)' || true)
  if [ -z "$hits" ]; then
    pass "no network calls in scripts/ or agents/"
  else
    fail "network reference found in executable skill content"
    printf '%s\n' "$hits" | head -5 | sed 's/^/      /'
  fi
}

# references/ is the other executable surface, and the one the offline check above does not read:
# a model told to run `npx depcruise` WILL run it, so a command documented in prose reaches the
# network just as surely as one in a script. Both patterns here pin a fix that was already made
# once and would otherwise be invisible to this suite.
check_documented_commands_are_offline() {
  local hits=""
  # `npx <pkg>` DOWNLOADS the package when it is not present. --no-install makes it fail loudly
  # instead, which is the only form safe to put in front of a model on an offline machine.
  # `npx X` is the METAVARIABLE, used by the prose that warns against the unguarded form; flagging
  # it would flag the warning rather than the command. A real package name is never a bare `X`.
  hits="$hits$(cd "$ROOT" && grep -rn -E 'npx ' ./md_*/references/ ./md_*/*.md 2>/dev/null \
        | grep -v -- '--no-install' | grep -v -E 'npx X([^A-Za-z0-9_-]|$)' || true)"
  # -mod=mod is the mode that lets the go command rewrite go.mod and FETCH the missing modules.
  # The prose may name it as the wrong answer; only the assignment form is a command.
  hits="$hits$(cd "$ROOT" && grep -rn -E 'GOFLAGS=-mod=mod' ./md_*/references/ ./md_*/*.md 2>/dev/null || true)"
  if [ -z "$hits" ]; then
    pass "every package-runner command in the docs carries its offline guard"
  else
    fail "a documented command would reach the network"
    printf '%s\n' "$hits" | head -5 | sed 's/^/      /'
  fi
}

check_documented_commands_carry_their_offline_guard() {
  # The previous check covers scripts/ and agents/ only, and it looks for obvious network verbs.
  # The real leak is subtler and lives in references/ and jobs/: a COPYABLE command for a tool
  # that resolves dependencies by default. `npx X` fetches X, `go list ./...` reaches
  # proxy.golang.org, `mvn`/`gradle`/`cargo` hit their repos. A model copies the row it is shown,
  # so every runnable command must carry its own guard on the spot — a guard in the row below is
  # a guard nobody copies.
  #
  # Scoped to avoid punishing prose: a backtick span of <=3 tokens is a NAME ("`go mod graph`"),
  # a line that argues against the command is skipped, and a `#` line in a shell script is a
  # comment, not a command.
  local out prog
  prog="$(mktemp "${TMPDIR:-/tmp}/netlint.XXXXXX.py")"
  cat >"$prog" <<'PY'
import os, re, sys
GUARD = {"npx": re.compile(r"--no-install"),
         "go": re.compile(r"GOPROXY=off|GOFLAGS=-mod=readonly"),
         "mvn": re.compile(r"(^|\s)-o(\s|$)|--offline"),
         "gradle": re.compile(r"--offline"),
         "cargo": re.compile(r"--offline")}
FORBIDDEN = re.compile(r"^(gradlew|\./gradlew|pip3?\s+install|npm\s+(install|i|ci)\b|apt-get"
                       r"|brew\s+install|gem\s+install|dotnet\s+restore|curl|wget|ssh|scp|gh\b"
                       r"|git\s+(clone|fetch|pull|push|ls-remote))")
NEG = re.compile(r"never|not optional|is wrong|refus|must not|breaks the offline|out of scope"
                 r"|no network|instead of downloading|fails instead|forbidden|banned|do not"
                 r"|don.t|rather than|prefer the system", re.I)
SPAN = re.compile(r"`([^`]+)`")

def commands(line, is_sh):
    if is_sh:
        return [line]
    out = []
    for s in SPAN.findall(line):
        out.extend(re.split(r"\s+·\s+|\s+\|\s+", s))
    return out

bad = []
for root in sys.argv[1:]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "tests", "__pycache__")]
        for fn in sorted(filenames):
            if not fn.endswith((".md", ".sh")) or fn == "install.sh":
                continue
            p = os.path.join(dirpath, fn)
            is_sh = fn.endswith(".sh")
            lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
            for i, line in enumerate(lines, 1):
                if NEG.search(line) or (is_sh and re.match(r"\s*#", line)):
                    continue
                # a shell command may be split across continuations, so the guard may be above it
                window = "\n".join(lines[max(0, i - 5):i]) if is_sh else line
                for cmd in commands(line, is_sh):
                    toks = cmd.strip().split()
                    if not toks:
                        continue
                    head = re.sub(r"^\W+", "", toks[0])
                    if FORBIDDEN.match(cmd.strip()) or FORBIDDEN.match(head):
                        bad.append(f"{p}:{i}: network command with no offline form: {cmd.strip()[:90]}")
                        break
                    if len(toks) <= 3:
                        continue
                    g = GUARD.get(head)
                    if g and not g.search(window):
                        bad.append(f"{p}:{i}: {head} command without its offline guard: {cmd.strip()[:90]}")
                        break
for b in bad:
    print(b)
PY
  out=$(cd "$ROOT" && python3 "$prog" ./md_*/ )
  rm -f -- "$prog"
  if [ -z "$out" ]; then
    pass "every copyable command carries its own offline guard"
  else
    fail "a documented command would reach the network as written"
    printf '%s\n' "$out" | head -5 | sed 's/^/      /'
  fi
}

check_no_webfetch_tools() {
  local hits
  hits=$(cd "$ROOT" && grep -rn -E 'tools:.*(WebFetch|WebSearch)' ./md_*/agents/ 2>/dev/null || true)
  if [ -z "$hits" ]; then
    pass "no bundled agent is granted WebFetch or WebSearch"
  else
    fail "an agent is granted a network tool"
    printf '%s\n' "$hits" | sed 's/^/      /'
  fi
}

check_scripts_are_stdlib_only() {
  local hits
  hits=$(cd "$ROOT" && grep -rn -E '^[[:space:]]*(import|from)[[:space:]]+(requests|httpx|urllib3|networkx|numpy|pandas|scipy|yaml|git)\b' \
        ./md_*/scripts/ 2>/dev/null || true)
  if [ -z "$hits" ]; then
    pass "measurement scripts import no third-party package"
  else
    fail "a script needs a third-party package (breaks the offline guarantee)"
    printf '%s\n' "$hits" | sed 's/^/      /'
  fi
}

# --------------------------------------------------------------- SECURITY ----

check_no_banned_auth_material() {
  local hits
  # Both halves require a VERB, symmetrically: the ban is on minting material, so `openssl req` and
  # `keytool -genkeypair` are the finding while the bare tool name is not. A policy file has to be
  # able to say "never run openssl/keytool to mint an auth credential" — naming the banned tool in a
  # prohibition is the opposite of shipping the guidance, and a check that cannot tell the two apart
  # forces the ban to be written in euphemism, which is how it stops being followed.
  hits=$(cd "$ROOT" && grep -rn -iE 'openssl (req|genrsa|genpkey|x509)|keytool +-(genkey|genkeypair|importcert|certreq|selfcert)|-----BEGIN [A-Z ]*PRIVATE KEY|self-signed' \
        --exclude-dir=.git --exclude=smoke.sh . 2>/dev/null || true)
  if [ -z "$hits" ]; then
    pass "no generated cert/key material and no cert-as-auth guidance"
  else
    fail "banned auth material or guidance present"
    printf '%s\n' "$hits" | head -5 | sed 's/^/      /'
  fi
}

check_no_secrets() {
  local hits
  hits=$(cd "$ROOT" && grep -rn -iE '(aws_secret_access_key|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|password[[:space:]]*=[[:space:]]*["'"'"'][^"'"'"']+)' \
        --exclude-dir=.git --exclude=smoke.sh . 2>/dev/null || true)
  if [ -z "$hits" ]; then
    pass "no credential-shaped literals"
  else
    fail "possible credential in the repo"
    printf '%s\n' "$hits" | head -5 | sed 's/^/      /'
  fi
}

check_no_unsafe_shell() {
  local hits
  hits=$(cd "$ROOT" && grep -rnE '\beval\b|\bsudo\b|chmod[[:space:]]+777|rm[[:space:]]+-rf[[:space:]]+/[^"'"'"'$]' \
        ./md_*/scripts/ install.sh 2>/dev/null | grep -vE ':[[:space:]]*#' || true)
  if [ -z "$hits" ]; then
    pass "no eval, sudo, chmod 777, or unrooted rm -rf in shipped shell"
  else
    fail "unsafe shell construct"
    printf '%s\n' "$hits" | sed 's/^/      /'
  fi
}

check_shell_syntax() {
  local bad=0 f
  for f in $(cd "$ROOT" && ls install.sh tests/smoke.sh ./md_*/scripts/*.sh 2>/dev/null); do
    bash -n "$ROOT/$f" 2>/dev/null || { fail "syntax error in $f"; bad=1; }
  done
  [ "$bad" -eq 0 ] && pass "every shipped shell script parses"
}

check_scripts_set_safe_flags() {
  # These scripts deliberately do NOT set -e: a cap violation is data, so they exit 0
  # with findings and reserve non-zero for "the scan could not run". They must still
  # set -u and pipefail so a typo or a broken pipe cannot silently produce empty output.
  local bad=0 f
  for f in $(cd "$ROOT" && ls ./md_*/scripts/*.sh 2>/dev/null); do
    grep -qE '^set -[a-z]*u' "$ROOT/$f"  || { fail "$f does not set -u"; bad=1; }
    grep -q 'pipefail' "$ROOT/$f"        || { fail "$f does not set pipefail"; bad=1; }
  done
  [ "$bad" -eq 0 ] && pass "measurement scripts set -u and pipefail"
}

check_installer_writes_nothing_on_dry_run() {
  local sandbox
  sandbox=$(mktemp -d)
  CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" \
    bash "$ROOT/install.sh" --dry-run >/dev/null 2>&1
  if [ -e "$sandbox/cfg" ]; then
    fail "install.sh --dry-run created $sandbox/cfg"
  else
    pass "install.sh --dry-run writes nothing"
  fi
  rm -rf -- "$sandbox"
}

check_installer_round_trip() {
  local sandbox out
  sandbox=$(mktemp -d)
  if ! out=$(CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" \
             bash "$ROOT/install.sh" 2>&1); then
    fail "install.sh failed: $(printf '%s' "$out" | tail -1)"
    rm -rf -- "$sandbox"; return
  fi
  local n
  n=$(ls "$sandbox/cfg/skills" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" -lt 1 ]; then
    fail "install.sh installed nothing"
  elif [ ! -f "$sandbox/cfg/skills"/*/SKILL.md ] 2>/dev/null; then
    # glob may expand to several; check each
    local ok=1 d
    for d in "$sandbox/cfg/skills"/*; do [ -f "$d/SKILL.md" ] || ok=0; done
    [ "$ok" -eq 1 ] && pass "install.sh installed $n skill(s), each with a reachable SKILL.md" \
                    || fail "an installed skill has no reachable SKILL.md"
  else
    pass "install.sh installed $n skill(s), each with a reachable SKILL.md"
  fi
  # A skill renamed in the checkout leaves a DANGLING link behind, and that is the case --uninstall
  # exists to clean. The loop guarded on `-e`, which follows the link and so could not see it: the
  # broken entry survived every uninstall and shadowed a later install of the same name. Plant one
  # pointing into this checkout (the ours/theirs test only accepts that) and require it gone.
  ln -s -- "$ROOT/md_this-skill-was-renamed-away" "$sandbox/cfg/skills/md_stale-name"
  CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" \
    bash "$ROOT/install.sh" --uninstall >/dev/null 2>&1
  if [ -L "$sandbox/cfg/skills/md_stale-name" ]; then
    fail "--uninstall left a dangling symlink it created behind"
  else
    pass "--uninstall removes a dangling symlink, not just a resolvable one"
  fi
  if ls "$sandbox/cfg/skills"/* "$sandbox/cfg/agents"/* >/dev/null 2>&1; then
    fail "install.sh --uninstall left files behind"
  else
    pass "install.sh --uninstall is clean"
  fi
  rm -rf -- "$sandbox"
}

check_installer_installs_the_bundled_agents() {
  # SKILL.md's fan-out contract names five bundled agents and treats their absence as a
  # documented fallback to `general-purpose`. An installer that silently ships only the skill
  # makes the fallback the ONLY path, so the agent-level write-scope and finding-contract rules
  # never load — the pipeline still answers, with none of the guard rails it claims.
  local sandbox want got
  sandbox=$(mktemp -d)
  want=$(cd "$ROOT" && ls ./md_*/agents/*.md 2>/dev/null | wc -l | tr -d ' ')
  [ "$want" -gt 0 ] || { info "no bundled agents to install"; rm -rf -- "$sandbox"; return; }
  CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" \
    bash "$ROOT/install.sh" >/dev/null 2>&1
  got=$(ls "$sandbox/cfg/agents"/*.md 2>/dev/null | wc -l | tr -d ' ')
  # Reachable, not merely present: a symlink to a path that moved installs a broken agent.
  local broken=0 f
  for f in "$sandbox/cfg/agents"/*.md; do [ -f "$f" ] || broken=1; done
  if [ "$got" = "$want" ] && [ "$broken" -eq 0 ]; then
    pass "install.sh installed all $want bundled agent(s), each readable"
  else
    fail "installed $got of $want bundled agents (unreadable: $broken)"
  fi
  rm -rf -- "$sandbox"
}

check_installer_stays_inside_its_two_roots() {
  # This exact leak happened: the tests sandboxed CLAUDE_CONFIG_DIR only, so `auto` mode saw the
  # REAL ~/.codex, installed there, and left a symlink into a temp dir that the test then deleted —
  # a dangling skill in the user's own config, produced by running the test suite. A test that can
  # modify the machine it is testing is worse than no test.
  local sandbox before_c before_x after_c after_x
  sandbox=$(mktemp -d)
  before_c=$(ls -A "$HOME/.claude/skills" 2>/dev/null | wc -l | tr -d ' ')
  before_x=$(ls -A "$HOME/.codex/skills" 2>/dev/null | wc -l | tr -d ' ')
  CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" \
    bash "$ROOT/install.sh" --codex >/dev/null 2>&1
  after_c=$(ls -A "$HOME/.claude/skills" 2>/dev/null | wc -l | tr -d ' ')
  after_x=$(ls -A "$HOME/.codex/skills" 2>/dev/null | wc -l | tr -d ' ')
  [ "$before_c" = "$after_c" ] && [ "$before_x" = "$after_x" ] \
    && pass "a sandboxed install touches neither real config root" \
    || fail "install leaked outside its roots (claude $before_c->$after_c, codex $before_x->$after_x)"
  rm -rf -- "$sandbox"
}

check_installer_installs_into_codex_home() {
  # Codex reads the same `<home>/skills/<name>/SKILL.md` layout, so the second host is one more
  # destination for the SAME directory — not a fork. Three properties matter and none is visible
  # from the Claude-only path: the skill lands and is reachable, `--no-codex` leaves the Codex home
  # untouched, and `--uninstall` takes the Codex symlink with it (a stale link there points at a
  # deleted checkout and Codex would surface the skill as broken rather than absent).
  local sandbox
  sandbox=$(mktemp -d)
  mkdir -p "$sandbox/codex"
  CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" \
    bash "$ROOT/install.sh" >/dev/null 2>&1
  # Count, never `[ -f <glob> ]`: with two or more skills installed the glob expands to two words and
  # `[ -f a b ]` is a usage error, so the check reported "nothing installed" the moment the repo
  # shipped its second skill. The assertion is "at least one reachable SKILL.md landed".
  local reachable=0 skillmd
  for skillmd in "$sandbox/codex/skills"/*/SKILL.md; do
    [ -f "$skillmd" ] && reachable=$((reachable + 1))
  done
  if [ "$reachable" -gt 0 ]; then
    pass "install.sh installs into a Codex home too, and all $reachable SKILL.md are reachable"
  else
    fail "install.sh installed nothing into the Codex home"
  fi
  CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" \
    bash "$ROOT/install.sh" --uninstall >/dev/null 2>&1
  ls "$sandbox/codex/skills"/* >/dev/null 2>&1 \
    && fail "--uninstall left a skill in the Codex home" \
    || pass "--uninstall clears the Codex home too"
  check_no_codex_writes_nothing
  rm -rf -- "$sandbox"
}

check_no_codex_writes_nothing() {
  # A separate sandbox, because the assertion is "not one byte", and reusing the one above would
  # be asserting that against a directory this test already wrote to.
  local sandbox n
  sandbox=$(mktemp -d)
  mkdir -p "$sandbox/codex"
  CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" \
    bash "$ROOT/install.sh" --no-codex >/dev/null 2>&1
  n=$(ls -A "$sandbox/codex" 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -eq 0 ] && pass "--no-codex writes nothing into the Codex home" \
                 || fail "--no-codex wrote $n entry/entries into the Codex home"
  rm -rf -- "$sandbox"
}

check_installer_clone_path_installs() {
  # The README's headline install is `curl … | bash`, which has no checkout and therefore always
  # takes the clone path. That path was broken and no test saw it: `resolve_source` is read with
  # `$( )`, so its progress line and `git reset --hard`'s "HEAD is now at …" were prepended to the
  # source directory and every remote install died on "could not resolve a source tree". Cloning
  # THIS repo over file:// exercises it without a network.
  local sandbox branch out
  sandbox=$(mktemp -d)
  mkdir -p "$sandbox/bin" "$sandbox/cfg"
  # install.sh alone, in a directory with no skills, is what forces the clone branch.
  cp "$ROOT/install.sh" "$sandbox/bin/install.sh"
  branch=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
  installer_clone_run "$sandbox" "$branch" install || {
    rm -rf -- "$sandbox"; return; }
  installer_clone_run "$sandbox" "$branch" update
  rm -rf -- "$sandbox"
}

installer_clone_run() {
  # Both runs assert the same thing — a skill arrived — because the first exercises `git clone`
  # and the second `git fetch`/`reset --hard`, and only the second could regress on git's chatter.
  local sandbox=$1 branch=$2 phase=$3 out flag=""
  [ "$phase" = update ] && flag="--update"
  out=$(CLAUDE_CONFIG_DIR="$sandbox/cfg" CODEX_HOME="$sandbox/codex" SKILL_LIB_REPO="file://$ROOT" \
        SKILL_LIB_BRANCH="$branch" bash "$sandbox/bin/install.sh" $flag 2>&1) || {
    fail "install.sh $phase from a clone failed: $(printf '%s' "$out" | tail -1)"; return 1; }
  # Count, do not test one path: `[ -f dir/*/SKILL.md ]` is a single-argument test, so the moment
  # the clone carries a SECOND skill the glob expands to two words and `[` dies on "too many
  # arguments" — a green suite that turns red on a commit that added nothing but a skill.
  # Count, and count THROUGH the symlink: the default install links `skills/<name>` at the
  # destination, and `find` without `-L` will not descend into a symlinked directory, so a
  # link-mode install could never satisfy this check. `[ -f ]` dereferences, which is the
  # property being asserted anyway — the host has to be able to read the SKILL.md.
  local landed=0 skillmd
  for skillmd in "$sandbox/cfg/skills"/*/SKILL.md; do
    [ -f "$skillmd" ] && landed=$((landed + 1))
  done
  [ "$landed" -gt 0 ] \
    && pass "install.sh installs from a fresh clone ($phase): $landed skill(s)" \
    || { fail "install.sh $phase from a clone left no reachable SKILL.md"; return 1; }
}

# ----------------------------------------------------------------- WIRING ----

check_documented_skill_paths_resolve() {
  # Docs and agents address the bundled scripts through `${CLAUDE_PLUGIN_ROOT}/skills/<name>/…` or
  # `${CLAUDE_SKILL_DIR}/…`. Both are runner-supplied, so a typo or a rename inside one of those
  # strings cannot fail until a real run, in the middle of a phase, as `bash: no such file`.
  # Substituting the real directory here is what turns that into a test failure instead.
  #
  # The repo is flat (`md_<name>/SKILL.md` at the top level) while the INSTALLED tree the variables
  # address is `<host>/skills/<name>/…`. So each variable gets both readings and one has to hold:
  # against the skill's own directory (the flat repo, and what SKILL_DIR always means), and — for
  # PLUGIN_ROOT with a `skills/<name>/` prefix — against that named sibling skill at the repo top
  # level. Accepting either is not a loosening: the tail after the anchor is still checked
  # character for character, so a renamed script or a misspelled reference still fails.
  local prog out
  prog="$(mktemp "${TMPDIR:-/tmp}/skillpath.XXXXXX.py")"
  cat >"$prog" <<'PY'
import os, re, sys
VAR = re.compile(r"\$\{CLAUDE_(?:PLUGIN_ROOT|SKILL_DIR)\}([A-Za-z0-9_./*-]*)")
bad = []
for root in sys.argv[1:]:
    # `root` is one skill directory, e.g. ./md_codegraph/ — its parent is the repo top level,
    # which is where a `skills/<name>/` tail has to be resolved now that the layout is flat.
    repo = os.path.dirname(root.rstrip("/")) or "."
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for name in files:
            if not name.endswith((".md", ".json")):
                continue
            path = os.path.join(base, name)
            text = open(path, encoding="utf-8", errors="replace").read()
            for match in VAR.finditer(text):
                tail = match.group(1).rstrip("/*.,`)").lstrip("/")
                # SKILL_DIR is the skill directory itself. PLUGIN_ROOT is the installed tree's
                # skills/ parent, so `skills/<name>/…` names a skill that is now a top-level
                # sibling; without that prefix it addresses the skill's own files.
                cand = [os.path.join(root, tail)]
                if "PLUGIN_ROOT" in match.group(0) and tail.startswith("skills/"):
                    cand.append(os.path.join(repo, tail[len("skills/"):]))
                if not any(os.path.exists(c) for c in cand):
                    bad.append(f"{os.path.relpath(path, root)}: {match.group(0)}")
for line in sorted(set(bad)):
    print(line)
PY
  out=$(cd "$ROOT" && python3 "$prog" ./md_*/ )
  rm -f -- "$prog"
  if [ -n "$out" ]; then
    fail "a documented \${CLAUDE_*} path does not exist"
    printf '%s\n' "$out" | sed 's/^/      /'
  else
    pass "every documented \${CLAUDE_*}/... path resolves to a real file"
  fi
}

check_documented_caps_keys_carry_a_severity() {
  # `caps.sh` emits `<metric>_<severity>` for every metric, with no exceptions. A doc that names
  # the bare metric as a totals key — `"unparseable": 0` — teaches a gate to read a key the tool
  # never prints, and `.get(key, 0) == 0` then passes forever on a repo full of unreadable files.
  local out
  out=$(cd "$ROOT" && python3 - ./md_*/ <<'PY'
import os, re, sys
METRICS = {"file_lines", "method_lines", "nesting", "loop_body", "else", "params",
           "public_members", "unparseable", "exempt_without_reason", "unbalanced_braces"}
SEV = ("_minor", "_major", "_exempt")
KEY = re.compile(r'"([a-z_]+)"\s*:')
bad = []
for root in sys.argv[1:]:
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(base, name)
            for number, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
                if line.lstrip().startswith("//"):
                    continue                      # a jsonc comment explaining the rule, not a key
                for key in KEY.findall(line):
                    if key in METRICS and not key.endswith(SEV):
                        bad.append(f"{path}:{number}: \"{key}\" has no severity suffix")
for line in bad:
    print(line)
PY
)
  if [ -n "$out" ]; then
    fail "a documented caps totals key is missing its severity suffix"
    printf '%s\n' "$out" | sed 's/^/      /'
  else
    pass "every documented caps totals key is spelled <metric>_<severity>"
  fi
}

check_documented_graph_keys_have_the_documented_type() {
  # Key spelling was already checked; the SHAPE was not. `specs/graph-report.md` documented
  # `hub_like` as a list of objects with medians and a `ratio_ok` flag, while every build emits a
  # plain `string[]` — so a consumer doing `h["node"]` raises TypeError, and a model that instead
  # "fills in" median_fan_in has fabricated a number, which the skill calls a hard error. Spelling
  # alone cannot catch that: only the real output, parsed, against the documented type.
  local script="$ROOT"/md_*/scripts/graph.sh
  # shellcheck disable=SC2086
  set -- $script
  [ -f "${1:-}" ] || { info "no graph.sh to test"; return; }
  local fx out rc=0
  fx=$(mktemp -d); mkdir -p "$fx/src"
  # A hub needs fan-in AND fan-out above the medians, so the fixture is a small star with a middle.
  printf 'import mid\n' > "$fx/src/one.py"
  printf 'import mid\n' > "$fx/src/two.py"
  printf 'import leaf_a\nimport leaf_b\nimport leaf_c\n' > "$fx/src/mid.py"
  printf 'x = 1\n' > "$fx/src/leaf_a.py"
  printf 'x = 2\n' > "$fx/src/leaf_b.py"
  printf 'x = 3\n' > "$fx/src/leaf_c.py"
  out=$(bash "$1" --root "$fx" --json 2>/dev/null) || rc=1
  rm -rf -- "$fx"
  [ "$rc" -eq 0 ] || { fail "graph.sh exited non-zero on the shape fixture"; return; }
  printf '%s' "$out" | python3 -c '
import json, sys
d = json.load(sys.stdin)
bad = []
for key in ("hub_like", "degraded"):
    v = d.get(key, [])
    if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
        bad.append(f"{key} must be a list of strings, got {v!r}")
for key in ("cycles", "ports", "nodes", "edges"):
    v = d.get(key, [])
    if not isinstance(v, list) or any(not isinstance(x, dict) for x in v):
        bad.append(f"{key} must be a list of objects, got {type(v).__name__}")
if not isinstance(d.get("fidelity"), str):
    bad.append("fidelity must be a string")
for line in bad:
    print(line, file=sys.stderr)
raise SystemExit(1 if bad else 0)
' && pass "graph.json keys carry the type specs/graph-report.md documents" \
  || fail "a graph.json key has a different type than its spec (see stderr)"
}

check_apply_gate_permits_multi_slice_progress() {
  # The sha gate said "spec sha must equal HEAD, else void". Slice 1 commits, HEAD moves, slice 2 is
  # declared void and the user is told to re-run `spec` — which rewrites the spec and voids the
  # approval they just gave. `apply all` could never reach slice 2, and neither could the bare
  # `/md_codegraph` resume that SKILL.md calls the whole interface. It failed CLOSED, so nothing was
  # unsafe; the feature was simply unreachable. Doc-level check, because `apply` is model-driven.
  local f="$ROOT"/md_*/jobs/apply.md
  # shellcheck disable=SC2086
  set -- $f
  [ -f "${1:-}" ] || { info "no apply.md to test"; return; }
  if grep -q 'rev-parse HEAD' "$1" && grep -q 'applied.md' "$1" \
     && python3 - "$1" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
i = text.find("rev-parse HEAD")
window = text[i:i + 400] if i >= 0 else ""
# The escape clause must sit in the sha check itself, not somewhere else in the file.
raise SystemExit(0 if ("applied.md" in window and re.search(r"\bor\b", window)) else 1)
PY
  then
    pass "the apply sha gate allows an earlier slice of the same spec to have moved HEAD"
  else
    fail "apply.md's sha gate voids the spec after slice 1, so multi-slice apply cannot run"
  fi
}

# check_plugin_manifest_targets_exist is GONE, not disabled. The flatten removed the plugin layer
# entirely: there are no `.claude-plugin/plugin.json` manifests left to validate, so the loop had
# nothing to iterate and printed PASS over an empty set — a green line asserting a property of
# files that do not exist, which is worse than no line at all. The invariant it protected (every
# path a manifest promises resolves) now lives in check_reference_index_targets_exist, which reads
# SKILL.md's own index, and in check_documented_skill_paths_resolve for `${CLAUDE_*}` paths. If a
# manifest layer ever comes back, this check has to come back with it.

check_reference_index_targets_exist() {
  local bad=0 s
  for s in $(cd "$ROOT" && ls ./md_*/SKILL.md 2>/dev/null); do
    local dir; dir=$(dirname -- "$ROOT/$s")
    local missing=""
    # Index rows look like: | `references/foo.md` | ... |
    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      [ -e "$dir/$rel" ] || missing="$missing$rel"$'\n'
    done < <(grep -oE '`(references|specs|jobs|scripts)/[A-Za-z0-9._/-]+`' "$ROOT/$s" | tr -d '`' | sort -u)
    if [ -n "$missing" ]; then
      fail "$s references files that do not exist"
      printf '%s' "$missing" | sed 's/^/      /'
      bad=1
    fi
  done
  [ "$bad" -eq 0 ] && pass "every path SKILL.md mentions exists"
}

check_every_file_is_reachable() {
  # A file nothing links to is a file no model will ever open. Every job and reference
  # must be cited by at least one OTHER file in the same skill. SKILL.md is the root and
  # is exempt; so is anything under specs/ (those are output templates, not read by name).
  # The candidate set is jobs/*.md and references/*.md ONLY, which is also what keeps a file at
  # the skill ROOT out of it: md_codegraph/SPEC.md is the skill's own design record and
  # md_*/agents/*.md are loaded by the runner from frontmatter, never cited by basename in prose,
  # so neither is orphanable — while both still COUNT as citers, because a reference an agent
  # tells the model to open is reachable exactly as a reference SKILL.md names.
  local bad=0 s
  for s in $(cd "$ROOT" && ls ./md_*/SKILL.md 2>/dev/null); do
    local dir; dir=$(dirname -- "$ROOT/$s")
    local orphans="" f rel
    for f in "$dir"/jobs/*.md "$dir"/references/*.md; do
      [ -e "$f" ] || continue
      rel="${f#$dir/}"
      # cited anywhere in the skill other than by itself?
      # NOTE: --include must precede the path; BSD grep does not permute options.
      if ! grep -rlF --include='*.md' -- "$(basename -- "$rel")" "$dir" \
           | grep -qv -- "^$f$"; then
        orphans="$orphans$rel"$'\n'
      fi
    done
    if [ -n "$orphans" ]; then
      fail "$s: files nothing links to (a model will never open these)"
      printf '%s' "$orphans" | sed 's/^/      /'
      bad=1
    fi
  done
  [ "$bad" -eq 0 ] && pass "every job and reference is cited by another file"
}

check_documented_flags_are_accepted() {
  # Docs that tell the model to run a flag the script rejects are worse than no docs:
  # the model runs it, gets exit 2, and has no fallback. Every `script.sh --flag` that
  # appears in shipped markdown must be in that script's own argument parser.
  local bad=0 sc
  for sc in $(cd "$ROOT" && ls ./md_*/scripts/*.sh 2>/dev/null); do
    local base; base=$(basename -- "$sc")
    local skill; skill=$(dirname -- "$(dirname -- "$ROOT/$sc")")
    # flags the parser actually handles, taken from its own case arms
    local accepted; accepted=$(grep -oE '^[[:space:]]*(-[a-z]\|)?--[a-z-]+\)' "$ROOT/$sc" \
                               | grep -oE '\-\-[a-z-]+' | sort -u)
    # Attribution matters: one doc line can name two scripts
    # ("caps.sh src/billing · graph.sh --cycles"). A flag belongs to the nearest
    # PRECEDING script name, so scan token by token rather than with one regex.
    local unknown
    unknown=$(printf '%s\n' "$accepted" | python3 -c '
import os, re, sys
accepted = {l.strip() for l in sys.stdin if l.strip()}
base, root = sys.argv[1], sys.argv[2]
tok = re.compile(r"[A-Za-z0-9_./-]+\.sh|--[a-z][a-z-]*")
bad = set()
for dirpath, _, names in os.walk(root):
    for n in names:
        if not n.endswith(".md"):
            continue
        with open(os.path.join(dirpath, n), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                owner = None
                for m in tok.findall(line):
                    if m.endswith(".sh"):
                        owner = os.path.basename(m)
                    elif owner == base and m not in accepted:
                        bad.add(m)
print("\n".join(sorted(bad)))
' "$base" "$skill")
    if [ -n "$unknown" ]; then
      fail "markdown documents flags $base does not accept"
      printf '%s\n' "$unknown" | sed "s|^|      $base |"
      bad=1
    fi
  done
  [ "$bad" -eq 0 ] && pass "every documented script flag is accepted by that script"
}

check_file_length_caps() {
  # AUTHORING.md §9 states two caps: SKILL.md <=250 because it is the router and is always in context,
  # and every other shipped prose file <=600 because a reference is loaded whole. Asserted in a
  # checklist, both drifted; here they cost nothing to keep true.
  local bad=0 f n
  for f in $(cd "$ROOT" && ls ./md_*/SKILL.md 2>/dev/null); do
    n=$(wc -l <"$ROOT/$f" | tr -d ' ')
    [ "$n" -le 250 ] || { fail "$f is $n lines (router cap 250)"; bad=1; }
  done
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    n=$(wc -l <"$f" | tr -d ' ')
    [ "$n" -le 600 ] || { fail "${f#$ROOT/} is $n lines (prose cap 600)"; bad=1; }
  done <<EOF
$(cd "$ROOT" && find ./md_*/ -name '*.md' -not -path '*/.git/*' | sed "s|^\.|$ROOT|")
EOF
  [ "$bad" -eq 0 ] && pass "SKILL.md is within 250 lines and every prose file within 600"
}

check_skill_frontmatter() {
  local bad=0 s
  for s in $(cd "$ROOT" && ls ./md_*/SKILL.md 2>/dev/null); do
    head -1 "$ROOT/$s" | grep -q '^---$' || { fail "$s has no YAML frontmatter"; bad=1; continue; }
    grep -qE '^name:' "$ROOT/$s" || { fail "$s frontmatter has no name:"; bad=1; }
    grep -qE '^description:' "$ROOT/$s" || { fail "$s frontmatter has no description:"; bad=1; }
  done
  [ "$bad" -eq 0 ] && pass "every SKILL.md has name and description frontmatter"
}

check_agent_frontmatter() {
  local bad=0 a
  local list; list=$(cd "$ROOT" && ls ./md_*/agents/*.md 2>/dev/null || true)
  [ -n "$list" ] || { info "no bundled agents to check"; return; }
  for a in $list; do
    local stem; stem=$(basename -- "$a" .md)
    head -1 "$ROOT/$a" | grep -q '^---$' || { fail "$a has no frontmatter"; bad=1; continue; }
    grep -qE "^name:[[:space:]]*$stem[[:space:]]*$" "$ROOT/$a" || { fail "$a: name does not match filename"; bad=1; }
    grep -qE '^description:' "$ROOT/$a" || { fail "$a has no description"; bad=1; }
  done
  [ "$bad" -eq 0 ] && pass "every agent has matching name and a description"
}

# --------------------------------------------------------------- BEHAVIOR ----

make_fixture() {
  FIXTURE=$(mktemp -d)
  mkdir -p "$FIXTURE"/pkg_a "$FIXTURE"/pkg_b "$FIXTURE"/pkg_c
  printf 'from pkg_b import beta\ndef alpha(): return beta()\n' > "$FIXTURE/pkg_a/__init__.py"
  printf 'from pkg_c import gamma\ndef beta(): return gamma()\n'  > "$FIXTURE/pkg_b/__init__.py"
  printf 'from pkg_a import alpha\ndef gamma(): return alpha()\n' > "$FIXTURE/pkg_c/__init__.py"
  python3 - "$FIXTURE/pkg_a/big.py" <<'PY'
import sys
body = "\n".join(f"    x{i} = {i}" for i in range(30))
src = f"""def wide(a, b, c, d, e, f):
{body}
    if a:
        if b:
            if c:
                return 1
    else:
        return 2
    return 0
"""
open(sys.argv[1], "w").write(src)
PY
  # file_lines is the cap most likely to be silently lost in a discovery rewrite, because a file
  # can only be measured if it was enumerated at all. 260 > the 250 hard cap, no imports, so the
  # cycle fixture above is unaffected.
  python3 -c 'open("'"$FIXTURE"'/pkg_a/long.py","w").write("x = 1\n" * 260)'
}

check_caps_finds_known_violations() {
  local script="$ROOT"/md_*/scripts/caps.sh
  # shellcheck disable=SC2086
  set -- $script
  [ -f "${1:-}" ] || { info "no caps.sh to test"; return; }
  local out
  out=$(bash "$1" --root "$FIXTURE" --json 2>/dev/null) || { fail "caps.sh exited non-zero"; return; }
  python3 - <<'PY' "$out" && pass "caps.sh finds the seeded method-length, params, nesting and else violations" \
                          || fail "caps.sh missed a seeded violation"
import json, sys
d = json.loads(sys.argv[1])
t = d.get("totals", {})
# worst_nesting is 2, not 3, and that is the DEFINITION not an off-by-one: SKILL.md measures
# nesting from the method body, so `for` + `if` is depth 1 and legal and only a third construct
# is a violation. The fixture seeds three (`if`/`for`/`if`) => depth 2, cap 1, one major.
# Pinned here on purpose: this convention is ambiguous enough to flip silently in a rewrite.
need = {"worst_method_lines": 30, "worst_params": 6, "worst_nesting": 2, "worst_else": 1,
        "nesting_major": 1, "worst_file_lines": 260, "file_lines_major": 1}
bad = [k for k, v in need.items() if int(t.get(k, 0)) < v]
if bad:
    print("under-reported:", bad, "got:", {k: t.get(k) for k in need}, file=sys.stderr)
    raise SystemExit(1)
PY
}

check_graph_cycles_mode_agrees_with_full() {
  # --cycles is a PROJECTION of --json, not a second measurement. If the two ever disagree,
  # the refine loop is being gated on a number the report does not contain.
  local script="$ROOT"/md_*/scripts/graph.sh
  # shellcheck disable=SC2086
  set -- $script
  [ -f "${1:-}" ] || { info "no graph.sh to test"; return; }
  local full slice
  full=$(bash "$1" --root "$FIXTURE" --json 2>/dev/null)   || { fail "graph.sh --json exited non-zero"; return; }
  slice=$(bash "$1" --root "$FIXTURE" --cycles 2>/dev/null) || { fail "graph.sh --cycles exited non-zero"; return; }
  bash "$1" --root "$FIXTURE" --cycles --text >/dev/null 2>&1 \
    || { fail "graph.sh --cycles --text exited non-zero"; return; }
  python3 - <<'PY' "$full" "$slice" && pass "graph.sh --cycles agrees with the full graph" \
                                    || fail "graph.sh --cycles disagrees with --json"
import json, sys
full, slice_ = json.loads(sys.argv[1]), json.loads(sys.argv[2])
if full.get("cycles") != slice_.get("cycles"):
    print("cycle lists differ", file=sys.stderr); raise SystemExit(1)
if full.get("totals", {}).get("cycles") != slice_.get("totals", {}).get("cycles"):
    print("cycle counts differ", file=sys.stderr); raise SystemExit(1)
# an absence claim must keep its caveats or a lexical scan reads as proof of acyclicity
if "degraded" in full and "degraded" not in slice_:
    print("--cycles dropped degraded[]", file=sys.stderr); raise SystemExit(1)
PY
}

check_graph_finds_known_cycle() {
  local script="$ROOT"/md_*/scripts/graph.sh
  # shellcheck disable=SC2086
  set -- $script
  [ -f "${1:-}" ] || { info "no graph.sh to test"; return; }
  local out
  out=$(bash "$1" --root "$FIXTURE" --json 2>/dev/null) || { fail "graph.sh exited non-zero"; return; }
  python3 - <<'PY' "$out" && pass "graph.sh finds the seeded 3-node cycle exactly" \
                          || fail "graph.sh did not report the seeded cycle correctly"
import json, sys
d = json.loads(sys.argv[1])
cycles = d.get("cycles", [])
if len(cycles) != 1:
    print(f"expected 1 cycle, got {len(cycles)}", file=sys.stderr); raise SystemExit(1)
scc = set(cycles[0].get("scc", []))
if scc != {"pkg_a", "pkg_b", "pkg_c"}:
    print(f"wrong SCC: {scc}", file=sys.stderr); raise SystemExit(1)
shape = cycles[0].get("shape")
if shape is not None and shape != "circle":
    print(f"3-node ring should be shape 'circle', got {shape!r}", file=sys.stderr); raise SystemExit(1)
PY
}

check_graph_resolves_bare_sibling_imports() {
  # `sys.path.insert(here); import sibling` is the flattest and most common intra-package idiom in
  # Python, and the skill's own scripts/lib/ is written in it. Refusing single-component targets
  # outright made graph.sh report edges: 0 over 13 modules that plainly import each other — a
  # cycle detector that reports a self-importing package as acyclic is worse than no detector.
  #
  # Both directions are pinned, because only the pair is the rule. Resolving a bare name is safe
  # ONLY while it stays scoped to the importer's own directory: that scope is what keeps
  # `import json` from binding to some distant json.py. A fix that resolved bare names globally
  # would pass the first assertion and fail the second, which is exactly what must not ship.
  local script="$ROOT"/md_*/scripts/graph.sh
  # shellcheck disable=SC2086
  set -- $script
  [ -f "${1:-}" ] || { info "no graph.sh to test"; return; }
  local fx out
  fx=$(mktemp -d)
  mkdir -p "$fx/lib" "$fx/other" "$fx/far"
  printf 'import beta\nx = beta\n'          > "$fx/lib/alpha.py"   # sibling: must be an edge
  printf 'y = 1\n'                          > "$fx/lib/beta.py"
  printf 'y = 2\n'                          > "$fx/other/beta.py"  # same stem, another folder
  printf 'y = 3\n'                          > "$fx/lib/zeta.py"    # UNIQUE stem, still not far/'s
  printf 'import json\nz = json\n'          > "$fx/lib/gamma.py"   # stdlib: stays unresolved
  # Two bare names from a folder that owns neither. `zeta` is deliberately unique in the tree, so
  # a fix that looked bare names up GLOBALLY would resolve it — the ambiguity guard cannot mask
  # the scope guard here, and the two failures stay distinguishable.
  printf 'import beta\nimport zeta\nw = 0\n' > "$fx/far/delta.py"
  out=$(bash "$1" --root "$fx" --json 2>/dev/null) || { rm -rf -- "$fx"; fail "graph.sh exited non-zero on the sibling fixture"; return; }
  rm -rf -- "$fx"
  python3 - <<'PY' "$out" && pass "a bare sibling import is an edge, a bare non-sibling import is not" \
                          || fail "bare-name import resolution is wrong (see stderr)"
import json, sys
d = json.loads(sys.argv[1])
edges = {(e["from"], e["to"]) for e in d.get("edges", [])}
# The safety property first: a false edge invents a cycle, which is a blocker. A missing edge is
# only blindness, so it is the second assertion, not the first.
stray = {(s, t) for (s, t) in edges if s in ("far.delta", "lib.gamma")}
if stray:
    print(f"a bare name resolved OUTSIDE the importer's directory: {sorted(stray)}", file=sys.stderr)
    raise SystemExit(1)
if ("lib.alpha", "lib.beta") not in edges:
    print(f"lib/alpha.py `import beta` did not resolve to its sibling; edges={sorted(edges)}",
          file=sys.stderr)
    raise SystemExit(1)
PY
}

check_relative_imports_do_not_invent_absolute_targets() {
  # `from ....far import y` written where only 2 package levels exist climbs PAST the root. Dropping
  # the package prefix while keeping `node.module` recorded it as a plain `far`, so any node in the
  # tree that happened to be called `far` acquired an edge no import expresses — an invented edge
  # invents a cycle, and a cycle is a blocker.
  #
  # Both directions again, because the off-by-one is the whole difficulty. `node.level` is the DOT
  # COUNT, so levels climbed is `level - 1`: `keep == 0` lands exactly ON the root and is LEGAL,
  # only `keep < 0` is the error. A fix that refuses `keep <= 0` silences the false edge and takes
  # a true one with it, and would pass the second assertion below while failing the first.
  local script="$ROOT"/md_*/scripts/graph.sh
  # shellcheck disable=SC2086
  set -- $script
  [ -f "${1:-}" ] || { info "no graph.sh to test"; return; }
  local fx out
  fx=$(mktemp -d)
  mkdir -p "$fx/a/b"
  printf 'y = 1\n'                        > "$fx/far.py"        # node id `far`, at the root
  printf 'from ...far import y\nq = y\n'  > "$fx/a/b/atroot.py" # level 3, pkg a.b: keep==0, LEGAL
  printf 'from ....far import y\nr = y\n' > "$fx/a/b/over.py"   # level 4: climbs above the root
  out=$(bash "$1" --root "$fx" --json 2>/dev/null) || { rm -rf -- "$fx"; fail "graph.sh exited non-zero on the relative-import fixture"; return; }
  rm -rf -- "$fx"
  python3 - <<'PY' "$out" && pass "a relative import past the root invents no edge, one landing on it still resolves" \
                          || fail "relative-import resolution is wrong (see stderr)"
import json, sys
d = json.loads(sys.argv[1])
edges = {(e["from"], e["to"]) for e in d.get("edges", [])}
if ("a.b.over", "far") in edges:
    print(f"an import climbing PAST the root became an absolute target; edges={sorted(edges)}",
          file=sys.stderr)
    raise SystemExit(1)
if ("a.b.atroot", "far") not in edges:
    print(f"an import landing exactly ON the root (keep==0) is legal and must resolve; "
          f"edges={sorted(edges)}", file=sys.stderr)
    raise SystemExit(1)
PY
}

check_graph_degrades_when_a_file_was_not_read() {
  # An unread file is a HOLE, and a hole hides the edge that would have closed a cycle. graph.sh
  # used to report `fidelity: native`, `cycles: 0` over a repo with a plain a→c→a cycle because
  # c.py would not parse: the tool said "exact measurement of an acyclic repo" about a repo it had
  # half read. verify.md gate G8 then flips from FAIL to PASS when a slice BREAKS the syntax of a
  # cycle partner, which turns the safety gate into a reward for the damage.
  #
  # Two causes, one verdict, because the word is what downstream reads: unparseable source, and a
  # file emit_path refused. caps.sh already got this right, and that asymmetry is what hid it.
  local script="$ROOT"/md_*/scripts/graph.sh
  # shellcheck disable=SC2086
  set -- $script
  [ -f "${1:-}" ] || { info "no graph.sh to test"; return; }
  local fx rc=0 out
  fx=$(mktemp -d); mkdir -p "$fx/src"
  printf 'import c\nimport big\n' > "$fx/src/a.py"
  printf 'import a\ndef f(:\n'    > "$fx/src/c.py"   # real cycle partner, unparseable
  printf 'import a\n%s\n'         "$(head -c 400 </dev/zero | tr '\0' '#')" > "$fx/src/big.py"
  # CG_MAX_FILE_BYTES makes the oversize case cheap: the cap is a knob precisely so the refusal
  # can be provoked without writing a 5 MiB fixture.
  out=$(CG_MAX_FILE_BYTES=200 bash "$1" --root "$fx" --json 2>/dev/null) || rc=1
  rm -rf -- "$fx"
  [ "$rc" -eq 0 ] || { fail "graph.sh exited non-zero on the partially-readable fixture"; return; }
  printf '%s' "$out" | python3 -c '
import json, sys
d = json.load(sys.stdin)
notes = " ".join(str(x) for x in (d.get("degraded") or []))
if d.get("fidelity") == "native":
    print("fidelity still claims native over a scan that skipped files", file=sys.stderr)
    raise SystemExit(1)
if "parse" not in notes or "CG_MAX_FILE_BYTES" not in notes:
    print(f"both causes must be named in degraded; got: {notes!r}", file=sys.stderr)
    raise SystemExit(1)
' && pass "a graph that could not read every file reports fidelity=degraded" \
  || fail "graph.sh overstated fidelity on an incomplete scan"
}

check_line_counts_are_exact() {
  # Two off-by-ones that pointed opposite ways, on the two numbers a reader compares side by side.
  # `wc -l` counts NEWLINES, so a 251-line file with no final newline measured 250 and landed as a
  # `minor` under the 250 hard cap it actually breaches — fitness test F7 (`*_major == 0`) stays
  # green on a file over the wall. `src.count("\n") + 1` went the other way and inflated every
  # `loc` by one per file, so a 5 000-file repo published a total 5 000 lines too big.
  local caps="$ROOT"/md_*/scripts/caps.sh
  local graph="$ROOT"/md_*/scripts/graph.sh
  # shellcheck disable=SC2086
  set -- $caps $graph
  [ -f "${1:-}" ] && [ -f "${2:-}" ] || { info "no scripts to test"; return; }
  local fx
  fx=$(mktemp -d); mkdir -p "$fx/src"
  python3 - "$fx/src" <<'PY'
import os, sys
d = sys.argv[1]
open(os.path.join(d, "ten.py"), "w").write("x = 1\n" * 10)          # exactly 10 lines
open(os.path.join(d, "over.py"), "w").write("x = 1\n" * 250 + "x = 1")  # 251, no final newline
PY
  bash "$1" --root "$fx" --json 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
worst = d.get("totals", {}).get("worst_file_lines")
if worst != 251:
    print(f"worst_file_lines should be 251 (no trailing newline), got {worst}", file=sys.stderr)
    raise SystemExit(1)
if d.get("totals", {}).get("file_lines_major", 0) != 1:
    print("a 251-line file must be a major against the 250 hard cap", file=sys.stderr)
    raise SystemExit(1)
' && pass "caps.sh counts an unterminated last line, so the hard cap cannot be evaded" \
  || fail "caps.sh miscounted file length"
  bash "$2" --root "$fx" --json 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
loc = {n["id"]: n["loc"] for n in d.get("nodes", [])}
want = {"src.ten": 10, "src.over": 251}
bad = {k: (loc.get(k), v) for k, v in want.items() if loc.get(k) != v}
if bad:
    print(f"loc is not the line count (got, want): {bad}", file=sys.stderr)
    raise SystemExit(1)
total = d.get("totals", {}).get("loc")
if total != 261:
    print(f"totals.loc should be 261, got {total}", file=sys.stderr)
    raise SystemExit(1)
' && pass "graph.sh loc equals caps.sh file_lines for the same file" \
  || fail "graph.sh loc disagrees with the real line count"
  rm -rf -- "$fx"
}

check_graph_text_mode_runs() {
  local script="$ROOT"/md_*/scripts/graph.sh
  # shellcheck disable=SC2086
  set -- $script
  [ -f "${1:-}" ] || return
  local out
  if out=$(bash "$1" --root "$FIXTURE" --text 2>&1) && [ -n "$out" ]; then
    pass "graph.sh --text renders"
  else
    fail "graph.sh --text failed: $(printf '%s' "$out" | tail -1)"
  fi
}

check_scripts_emit_valid_json() {
  local bad=0 s
  for s in $(cd "$ROOT" && ls ./md_*/scripts/*.sh 2>/dev/null); do
    local out
    out=$(bash "$ROOT/$s" --root "$FIXTURE" --json 2>/dev/null) || { fail "$s exited non-zero"; bad=1; continue; }
    printf '%s' "$out" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null \
      || { fail "$s did not emit valid JSON"; bad=1; }
  done
  [ "$bad" -eq 0 ] && pass "every script emits valid JSON on --json"
}

tree_digest() {
  # CONTENTS, not just the file list. Hashing `find` output alone would pass a script that
  # rewrote every file in place, which is the exact failure this check exists to catch.
  ( cd "$1" && find . -type f -exec shasum {} + 2>/dev/null | sort ) | shasum | cut -d' ' -f1
}

check_scripts_are_read_only() {
  local before after
  before=$(tree_digest "$FIXTURE")
  local s
  for s in $(cd "$ROOT" && ls ./md_*/scripts/*.sh 2>/dev/null); do
    bash "$ROOT/$s" --root "$FIXTURE" --json >/dev/null 2>&1
  done
  after=$(tree_digest "$FIXTURE")
  if [ "$before" = "$after" ]; then
    pass "measurement scripts do not modify the analysed tree (contents, not just names)"
  else
    fail "a script wrote into the analysed tree"
  fi
}

# ------------------------------------------------------------- HOSTILE INPUT ----
# The scripts analyse code they did not write. Every check below corresponds to a defect that
# was live while all other checks passed, which is the reason this group exists at all.

hostile_fixture() {
  # Returns a path. Caller must rm -rf it.
  local d; d=$(mktemp -d "${TMPDIR:-/tmp}/cghostile.XXXXXX")
  mkdir -p "$d/src"
  python3 - "$d/src" <<'PY'
import os, sys
d = sys.argv[1]
body = "def f(a, b, c, d, e, g):\n" + "    x = 1\n" * 40
for name in ("ok.py", "has space.py", "quo'te.py", "$(touch PWNED_SUBST).py",
             "`touch PWNED_BT`.py", ";touch PWNED_SEMI;.py", "back\\slash.py",
             "esc\\nnot-a-newline.ts", "long.py"):
    open(os.path.join(d, name), "w").write(body)
open(os.path.join(d, "real\nnewline.py"), "w").write(body)   # a REAL newline in the name
# A bare CR is the newline's quieter twin: the newline check caught `\n` only, so `\r` travelled
# into the JSON as a raw control byte and made the WHOLE document unparseable at exit 0 — one
# `touch` denying every dimension of every run. Both must be refused, not just the one.
open(os.path.join(d, "carriage\rreturn.py"), "w").write(body)
open(os.path.join(d, "escape\x1bchar.ts"), "w").write(body)
open(os.path.join(d, "long.py"), "w").write("x = 1\n" * 300)
PY
  ln -s /etc/passwd "$d/src/leak.py"
  printf '%s' "$d"
}

check_hostile_names_cannot_inject_or_escape() {
  local d; d=$(hostile_fixture)
  local out rc=0
  rm -f PWNED_SUBST PWNED_BT PWNED_SEMI "$d"/PWNED_* 2>/dev/null || true
  local s
  for s in $(cd "$ROOT" && ls ./md_*/scripts/*.sh 2>/dev/null); do
    out=$(bash "$ROOT/$s" --root "$d" --json 2>/dev/null) || true
    # 1. output must still be parseable: a filename must never be a JSON injection point
    printf '%s' "$out" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null \
      || { fail "$(basename "$s"): a hostile filename broke --json"; rc=1; }
    # 2. no path may be reported from outside the analysed tree
    printf '%s' "$out" | python3 - <<'PY' || rc=1
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    raise SystemExit(0)          # already reported by check 1
for v in d.get("violations", []) or []:
    f = str(v.get("file", ""))
    if f.startswith("/") or f.startswith(".."):
        print(f"out-of-tree path reported: {f!r}", file=sys.stderr)
        raise SystemExit(1)
PY
    # 3. a symlink out of the tree must not be read
    printf '%s' "$out" | grep -q 'leak.py' \
      && { fail "$(basename "$s"): followed a symlink out of the analysed tree"; rc=1; }
  done
  # 4. nothing may have been executed
  if ls PWNED_* "$d"/PWNED_* >/dev/null 2>&1; then
    fail "a filename was executed as a command"; rc=1
  fi
  rm -rf -- "$d"
  [ "$rc" -eq 0 ] && pass "hostile filenames: no injection, no execution, no out-of-tree read"
}

check_unsafe_names_are_declared_not_silently_dropped() {
  # Skipping a file is the right call; skipping it SILENTLY overstates coverage. A file the
  # scanner cannot carry must appear in degraded and must pull fidelity off "native", or a
  # hostile repo hides every violation by renaming one file.
  local d; d=$(hostile_fixture)
  local script="$ROOT"/md_*/scripts/caps.sh
  # shellcheck disable=SC2086
  set -- $script
  if [ ! -f "${1:-}" ]; then info "no caps.sh to test"; rm -rf -- "$d"; return; fi
  bash "$1" --root "$d" --json 2>/dev/null \
    | python3 -c '
import json, sys
d = json.load(sys.stdin)
notes = " ".join(str(x) for x in (d.get("degraded") or []))
if "newline" not in notes:
    print("a newline-named file was skipped with no note in degraded", file=sys.stderr)
    raise SystemExit(1)
if d.get("fidelity") == "native":
    print("fidelity still claims native after skipping a file", file=sys.stderr)
    raise SystemExit(1)
' && pass "a file that cannot be scanned is declared in degraded, not hidden" \
  || fail "a skipped file was not declared"
  rm -rf -- "$d"
}

check_metacharacter_root_still_reports() {
  # A `|` or `&` in the analysed PATH used to be interpolated into a sed expression, so the
  # whole scan came back empty and exit 0 — a clean report on a dirty repo, the worst output
  # this tool can produce.
  local base; base=$(mktemp -d "${TMPDIR:-/tmp}/cgmeta.XXXXXX")
  local rc=0 d
  for frag in 'pipe|dir' 'amp&dir' 'sp ace' "quo'te"; do
    d="$base/$frag"; mkdir -p "$d"
    printf 'x = 1\n%.0s' $(seq 300) > "$d/big.py"
    local out
    out=$(bash "$ROOT"/md_*/scripts/caps.sh --root "$d" --json 2>/dev/null) || true
    printf '%s' "$out" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if not d.get("totals", {}).get("file_lines_major"):
    print("no file_lines violation reported:", d.get("totals"), file=sys.stderr)
    raise SystemExit(1)
' 2>/dev/null || { fail "caps.sh reported nothing for a root named '$frag'"; rc=1; }
  done
  rm -rf -- "$base"
  [ "$rc" -eq 0 ] && pass "a metacharacter in the analysed path cannot fake a clean report"
}

check_target_git_config_is_not_honoured() {
  # `core.fsmonitor` is a git config key whose value git EXECUTES. The analysed repo owns its
  # own .git/config, so honouring it means `git clone <hostile> && analyse` runs their command.
  command -v git >/dev/null 2>&1 || { info "no git; skipping target-config check"; return; }
  local d marker
  d=$(mktemp -d "${TMPDIR:-/tmp}/cggit.XXXXXX")
  marker="$d/EXECUTED"
  mkdir -p "$d/src"
  printf 'x = 1\n%.0s' $(seq 300) > "$d/src/a.py"
  printf '#!/bin/sh\ntouch %s\n' "$marker" > "$d/payload.sh"
  chmod +x "$d/payload.sh"
  git -C "$d" init -q >/dev/null 2>&1
  git -C "$d" config core.fsmonitor "$d/payload.sh"
  rm -f "$marker"
  local s rc=0
  for s in $(cd "$ROOT" && ls ./md_*/scripts/*.sh 2>/dev/null); do
    bash "$ROOT/$s" --root "$d" --json >/dev/null 2>&1
    [ -e "$marker" ] && { fail "$(basename "$s"): ran a command from the target's git config"; rc=1; }
    rm -f "$marker"
  done
  rm -rf -- "$d"
  [ "$rc" -eq 0 ] && pass "the analysed repo's git config cannot execute anything"
}

check_copied_caps_agree_across_skills() {
  # md_policy-code-review carries its OWN copy of the structural caps on purpose: it must rule from a
  # bare checkout with no sibling skill installed. A copy that can drift silently is worse than a
  # dependency, so the drift is what this check forbids — the two tables must agree row by row on
  # every limit they share, and codegraph's is the source.
  local source_table copy_table
  source_table=$(cd "$ROOT" && ls ./md_codegraph/SKILL.md 2>/dev/null | head -1)
  copy_table=$(cd "$ROOT" && ls ./md_policy-code-review/references/graph-policy.md 2>/dev/null | head -1)
  if [ -z "$source_table" ] || [ -z "$copy_table" ]; then
    return  # one of the two skills is not in this checkout; nothing to compare
  fi
  # Normalize a markdown cap row to "label|warn|hard": drop bold, backticks and the resolution cell.
  local norm='
    /^\| *(File length|Method length|Nesting depth in a method|Loop body length|`?else`?|Parameters|Public members per class)/ {
      gsub(/\*\*/, ""); gsub(/`/, "");
      split($0, c, "|");
      for (i = 2; i <= 4; i++) { gsub(/^ +| +$/, "", c[i]) }
      print c[2] "|" c[3] "|" c[4];
    }'
  local a b diffout
  a=$(cd "$ROOT" && awk "$norm" "$source_table" | sort)
  b=$(cd "$ROOT" && awk "$norm" "$copy_table" | sort)
  if [ -z "$a" ] || [ -z "$b" ]; then
    fail "could not read a cap table out of $source_table or $copy_table"
    return
  fi
  # Compare only the rows both tables carry: the copy may add caps (methods per port, inheritance
  # depth) that the router's abbreviated table leaves to references/laws.md.
  diffout=$(comm -3 <(printf '%s\n' "$a") <(printf '%s\n' "$b") \
            | awk -F'|' 'NF { print $1 }' | sed 's/^\t//' | sort -u \
            | while IFS= read -r label; do
                printf '%s\n' "$a" | grep -q "^$label|" && printf '%s\n' "$b" | grep -q "^$label|" \
                  && printf '%s: codegraph says %s / policy says %s\n' "$label" \
                       "$(printf '%s\n' "$a" | grep "^$label|")" "$(printf '%s\n' "$b" | grep "^$label|")"
              done)
  if [ -z "$diffout" ]; then
    pass "the copied structural caps still agree with codegraph's numbers"
  else
    fail "md_policy-code-review's cap copy has drifted from md_codegraph"
    printf '%s\n' "$diffout" | head -5 | sed 's/^/      /'
  fi
}

# ------------------------------------------------------------------- main ----

head2 "OFFLINE"
check_no_network_in_skills
check_documented_commands_are_offline
check_documented_commands_carry_their_offline_guard
check_no_webfetch_tools
check_scripts_are_stdlib_only

head2 "SECURITY"
check_no_banned_auth_material
check_no_secrets
check_no_unsafe_shell
check_shell_syntax
check_scripts_set_safe_flags
check_installer_writes_nothing_on_dry_run
check_installer_round_trip
check_installer_installs_the_bundled_agents
check_installer_clone_path_installs
check_installer_installs_into_codex_home
check_installer_stays_inside_its_two_roots

head2 "WIRING"
check_documented_skill_paths_resolve
check_documented_caps_keys_carry_a_severity
check_documented_graph_keys_have_the_documented_type
check_apply_gate_permits_multi_slice_progress
check_reference_index_targets_exist
check_every_file_is_reachable
check_documented_flags_are_accepted
check_file_length_caps
check_skill_frontmatter
check_agent_frontmatter
check_copied_caps_agree_across_skills

head2 "BEHAVIOR"
make_fixture
check_caps_finds_known_violations
check_graph_finds_known_cycle
check_graph_cycles_mode_agrees_with_full
check_graph_resolves_bare_sibling_imports
check_relative_imports_do_not_invent_absolute_targets
check_graph_degrades_when_a_file_was_not_read
check_line_counts_are_exact
check_graph_text_mode_runs
check_scripts_emit_valid_json
check_scripts_are_read_only

# The adversarial half. These run LAST because each builds its own hostile fixture and the point
# is not "does the tool work" but "does it still refuse". Every check here pins a fix that has
# already been made once: a filename that injects JSON, a filename that escapes the tree, a root
# full of shell metacharacters, and a repo whose own git config asks to run a command. Without
# these the fixes are invisible to the suite and can be refactored away silently — which is the
# only way a security fix normally dies.
head2 "HOSTILE INPUT"
check_hostile_names_cannot_inject_or_escape
check_unsafe_names_are_declared_not_silently_dropped
check_metacharacter_root_still_reports
check_target_git_config_is_not_honoured

printf '\n%s\n' "-----------------------------------------"
printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
