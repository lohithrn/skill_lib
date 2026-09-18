#!/usr/bin/env bash
#
# install.sh — install or update the skills in this repo into ~/.claude/skills/
#
#   Local checkout:  bash install.sh
#   No checkout:     curl -fsSL https://raw.githubusercontent.com/lohithrn/skill_lib/main/install.sh | bash
#   Update later:    bash install.sh --update      (or re-run the curl line)
#
# Default install mode is a symlink, so `--update` on a checkout is instant and skills
# always reflect the working tree. Use --copy for a detached snapshot.
#
# This script writes under $CLAUDE_DIR (default ~/.claude) and, in --copy mode only, a
# mktemp staging directory it removes on exit. It never executes code from the repo it
# installs, never needs sudo, and touches nothing else.

set -euo pipefail
IFS=$'\n\t'
umask 022

REPO_URL="${SKILL_LIB_REPO:-https://github.com/lohithrn/skill_lib.git}"
REPO_BRANCH="${SKILL_LIB_BRANCH:-main}"
# Fail with a remedy rather than a raw `HOME: unbound variable` from set -u.
if [ -z "${CLAUDE_CONFIG_DIR:-}" ] && [ -z "${HOME:-}" ]; then
  printf 'error: neither CLAUDE_CONFIG_DIR nor HOME is set; set one and re-run\n' >&2
  exit 1
fi
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SKILLS_DIR="$CLAUDE_DIR/skills"
AGENTS_DIR="$CLAUDE_DIR/agents"
CACHE_DIR="$CLAUDE_DIR/skill_lib"

# Codex reads the SAME layout — `<codex home>/skills/<name>/SKILL.md`, frontmatter `name` +
# `description` — so one skill directory serves both hosts and neither gets a divergent copy.
# CODEX_HOME is Codex's own relocation variable; honouring it is what makes this testable.
# Default is `auto`: install there when a Codex home already exists, never create one uninvited.
CODEX_DIR="${CODEX_HOME:-${HOME:-/nonexistent}/.codex}"
CODEX_SKILLS_DIR="$CODEX_DIR/skills"
CODEX=auto

MODE=link
ACTION=install
DRY_RUN=0
FORCE_CLONE=0

say()  { printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }
# `resolve_source` is read with `$( )`, so anything it prints to STDOUT becomes part of the path.
# Progress from inside a command substitution therefore goes to stderr — otherwise "==> cloning …"
# is prepended to the source directory and every clone/update install dies on `[ -d "$SRC" ]`.
step() { printf '%s\n' "$*" >&2; }
# Same trap, one level down: `git reset --hard` and `git pull` report on STDOUT ("HEAD is now
# at …", "Fast-forward"), which lands in $SRC exactly like a progress line would. Every git call
# made inside resolve_source goes through this, so no future git chatter can corrupt the path.
git_step() { run "$@" >&2; }
run()  {
  if [ "$DRY_RUN" -eq 1 ]; then
    { printf '  would: '; printf '%s ' "$@"; printf '\n'; } >&2
  else
    "$@"
  fi
}
done_msg() { [ "$DRY_RUN" -eq 1 ] || say "$*"; }

usage() {
  cat <<'EOF'
Usage: install.sh [options]

  --update       fetch the latest revision before installing (clones if needed)
  --copy         copy files instead of symlinking (detached snapshot)
  --link         symlink into the checkout (default)
  --list         list installed skills and their sources, then exit
  --uninstall    remove skills this script installed, then exit
  --codex        also install into Codex, creating its skills dir if needed
  --no-codex     install for Claude Code only
  --dry-run      print what would happen, change nothing
  -h, --help     this text

Hosts: Claude Code always; Codex too when a Codex home already exists (both read
<host>/skills/<name>/SKILL.md, so it is the same directory, not a second copy).
Codex has no subagent files, so the fan-out falls back as SKILL.md documents.

Environment:
  CLAUDE_CONFIG_DIR   config root                (default: ~/.claude)
  CODEX_HOME          Codex config root          (default: ~/.codex)
  SKILL_LIB_REPO      repo to clone when needed  (default: the public skill_lib repo)
  SKILL_LIB_BRANCH    branch to track            (default: main)
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --update)    FORCE_CLONE=1 ;;
    --copy)      MODE=copy ;;
    --link)      MODE=link ;;
    --list)      ACTION=list ;;
    --uninstall) ACTION=uninstall ;;
    --codex)     CODEX=yes ;;
    --no-codex)  CODEX=no ;;
    --dry-run)   DRY_RUN=1 ;;
    -h|--help)   usage; exit 0 ;;
    *)           die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

# --- locate the source tree -------------------------------------------------
# A source tree is any directory holding <skill_dir>/skills/<name>/SKILL.md.

has_skills() {
  local root=$1 d
  for d in "$root"/*/skills/*/; do
    [ -f "$d/SKILL.md" ] && return 0
  done
  return 1
}

script_dir() {
  local src=${BASH_SOURCE[0]:-}
  [ -n "$src" ] && [ -f "$src" ] || return 1
  cd -- "$(dirname -- "$src")" && pwd -P
}

sync_cache() {
  command -v git >/dev/null 2>&1 || die "git is required to fetch $REPO_URL"
  case "$REPO_URL" in
    https://*|file://*|/*) ;;
    *) die "refusing non-https repo URL: $REPO_URL" ;;
  esac
  if [ -d "$CACHE_DIR/.git" ]; then
    step "==> updating $CACHE_DIR"
    git_step git -C "$CACHE_DIR" fetch --depth 1 origin "$REPO_BRANCH"
    git_step git -C "$CACHE_DIR" checkout -q "$REPO_BRANCH"
    git_step git -C "$CACHE_DIR" reset --hard -q "origin/$REPO_BRANCH"
  else
    step "==> cloning $REPO_URL into $CACHE_DIR"
    git_step mkdir -p "$(dirname -- "$CACHE_DIR")"
    git_step git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$CACHE_DIR"
  fi
  printf '%s' "$CACHE_DIR"
}

resolve_source() {
  local here
  if [ "$FORCE_CLONE" -eq 0 ] && here=$(script_dir) && has_skills "$here"; then
    printf '%s' "$here"
    return 0
  fi
  if [ "$FORCE_CLONE" -eq 1 ] && here=$(script_dir) && [ -d "$here/.git" ] && has_skills "$here"; then
    step "==> updating checkout $here"
    git_step git -C "$here" pull --ff-only -q
    printf '%s' "$here"
    return 0
  fi
  sync_cache
}

# --- placing one skill, for either host -------------------------------------
# Both hosts read `<home>/skills/<name>/SKILL.md`, so the placement rule is one rule. It lives in
# two functions rather than one because "make room at the destination" and "put the skill there"
# fail for different reasons and the first must be able to refuse without the second running.

# Preserve anything already there that we did not put there. A symlink is only OURS if it points
# into the cache or the source tree — a user's own link to their own skill is not ours to delete,
# and --uninstall never restores backups, so a silent rm is unrecoverable.
clear_destination() {
  local dest=$1 label=$2 existing backup
  backup="$dest.backup.$(date +%Y%m%d%H%M%S)"
  if [ -L "$dest" ]; then
    existing=$(readlink -- "$dest" || true)
    case "$existing" in
      "$CACHE_DIR"/*|"$SRC"/*) run rm -- "$dest"; return 0 ;;
    esac
    warn "  existing $label is a link this installer did not create ($existing) -> moving to $(basename -- "$backup")"
    run mv -- "$dest" "$backup"
    return 0
  fi
  [ -e "$dest" ] || return 0
  warn "  existing $label was not installed by this script -> moving to $(basename -- "$backup")"
  run mv -- "$dest" "$backup"
}

place_skill() {
  local skill=$1 dest=$2 label=$3 stage
  if [ "$MODE" = link ]; then
    run ln -s -- "$skill" "$dest"
    done_msg "  linked $label"
    return 0
  fi
  if [ "$DRY_RUN" -eq 1 ]; then stage='<tmpdir>'; else
    stage=$(mktemp -d "${TMPDIR:-/tmp}/skill_lib.XXXXXX"); fi
  copy_tree "$skill" "$stage/$(basename -- "$dest")"
  run mv -- "$stage/$(basename -- "$dest")" "$dest"
  run rm -rf -- "$stage"
  done_msg "  copied $label"
}

# __pycache__ is gitignored, so it is never pushed — but it IS present in a working tree that has
# run the scanners, and a copy install would ship stale bytecode into the user's config directory.
copy_tree() {
  local from=$1 to=$2
  if command -v rsync >/dev/null 2>&1; then
    run rsync -a --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' -- "$from/" "$to/"
    return 0
  fi
  run mkdir -p "$to"
  run cp -R -- "$from/." "$to/"
  run find "$to" -name '__pycache__' -type d -prune -exec rm -rf -- {} +
}

# --- list / uninstall -------------------------------------------------------

if [ "$ACTION" = list ]; then
  [ -d "$SKILLS_DIR" ] || { say "no skills installed ($SKILLS_DIR does not exist)"; exit 0; }
  found=0
  for d in "$SKILLS_DIR"/*; do
    [ -e "$d" ] || continue
    [ -f "$d/SKILL.md" ] || [ -L "$d" ] || continue
    case "$d" in *.backup.*) continue ;; esac
    found=1
    if [ -L "$d" ]; then say "$(basename -- "$d")  ->  $(readlink -- "$d")"
    else                  say "$(basename -- "$d")  (copy)"; fi
  done
  [ "$found" -eq 1 ] || say "no skills installed in $SKILLS_DIR"
  for d in "$AGENTS_DIR"/*.md; do
    [ -e "$d" ] || continue
    if [ -L "$d" ]; then say "agent $(basename -- "$d")  ->  $(readlink -- "$d")"
    else                  say "agent $(basename -- "$d")  (copy)"; fi
  done
  for d in "$CODEX_SKILLS_DIR"/*; do
    [ -e "$d" ] || continue
    [ -f "$d/SKILL.md" ] || [ -L "$d" ] || continue
    case "$d" in *.backup.*) continue ;; esac
    if [ -L "$d" ]; then say "codex $(basename -- "$d")  ->  $(readlink -- "$d")"
    else                  say "codex $(basename -- "$d")  (copy)"; fi
  done
  exit 0
fi

if [ "$ACTION" = uninstall ]; then
  src=$(script_dir || true)
  removed=0
  for d in "$SKILLS_DIR"/*; do
    [ -e "$d" ] || continue
    name=$(basename -- "$d")
    if [ -L "$d" ]; then
      target=$(readlink -- "$d")
      case "$target" in
        "$CACHE_DIR"/*|"${src:-/nonexistent}"/*)
          say "==> removing symlink $name"; run rm -- "$d"; removed=1 ;;
        *) warn "skipping $name (symlink outside this repo: $target)" ;;
      esac
    fi
  done
  for d in "$AGENTS_DIR"/*.md; do
    [ -L "$d" ] || continue
    target=$(readlink -- "$d")
    case "$target" in
      "$CACHE_DIR"/*|"${src:-/nonexistent}"/*)
        say "==> removing agent symlink $(basename -- "$d")"; run rm -- "$d"; removed=1 ;;
      *) warn "skipping agent $(basename -- "$d") (symlink outside this repo: $target)" ;;
    esac
  done
  # Same ours/theirs test in the Codex home: a symlink pointing into the cache or this checkout is
  # ours, anything else is the user's and stays. Copies are left for the same reason as above.
  for d in "$CODEX_SKILLS_DIR"/*; do
    [ -L "$d" ] || continue
    target=$(readlink -- "$d")
    case "$target" in
      "$CACHE_DIR"/*|"${src:-/nonexistent}"/*)
        say "==> removing codex symlink $(basename -- "$d")"; run rm -- "$d"; removed=1 ;;
      *) warn "skipping codex $(basename -- "$d") (symlink outside this repo: $target)" ;;
    esac
  done
  [ "$removed" -eq 1 ] || say "nothing to uninstall (copied skills must be removed by hand)"
  say "note: $CACHE_DIR left in place; delete it manually if you want it gone"
  exit 0
fi

# --- install ----------------------------------------------------------------

SRC=$(resolve_source)
# In dry-run the clone did not happen, so the cache path is a plan, not a directory. Reporting
# "could not resolve a source tree" for a run that was told to change nothing is a false error.
if [ "$DRY_RUN" -eq 1 ] && [ ! -d "$SRC" ]; then
  say "dry run: would clone $REPO_URL ($REPO_BRANCH) into $SRC, then install from it"
  say "dry run: nothing was changed"
  exit 0
fi
[ -n "$SRC" ] && [ -d "$SRC" ] || die "could not resolve a source tree"
has_skills "$SRC" || die "no skills found under $SRC (expected */skills/*/SKILL.md)"

say "==> source:      $SRC"
say "==> destination: $SKILLS_DIR  (mode: $MODE)"
run mkdir -p "$SKILLS_DIR"

installed=0
claimed=""
for skill in "$SRC"/*/skills/*/; do
  skill=${skill%/}
  [ -f "$skill/SKILL.md" ] || continue
  name=$(basename -- "$skill")
  dest="$SKILLS_DIR/$name"

  # A skill NAME is the install identity, but the repo layout is */skills/<name>/, so two
  # skill directories can carry the same name. Installing both would silently leave one
  # unreachable and still report "installed 2". Refuse instead: the layout is meant to grow.
  case "$claimed" in
    *"|$name|"*) die "two skills are both named '$name' (second: $skill) — rename one; the install name is the directory name under skills/" ;;
  esac
  claimed="$claimed|$name|"

  clear_destination "$dest" "$name"
  place_skill "$skill" "$dest" "$name"
  # Counted only after the link or copy actually landed, so the summary cannot overstate.
  installed=$((installed + 1))
done

[ "$installed" -gt 0 ] || die "installed nothing"

# --- bundled subagents ------------------------------------------------------
# `skills/codegraph/SKILL.md` fans out to `codegraph-cartographer`, `-inspector`, `-architect`,
# `-adversary` and `-surgeon`. Without them every dimension falls back to `general-purpose` with
# the job file inlined — the pipeline still runs, but the agent-level guard rails (write-scope,
# the seven-field finding contract, the ≤25-line return) come back as prose instead of as the
# agent's own definition. They install as flat files, one per agent, so the same ours/theirs
# backup rule applies per file.
agents=0
for agent in "$SRC"/*/agents/*.md; do
  [ -f "$agent" ] || continue
  [ "$agents" -ne 0 ] || run mkdir -p "$AGENTS_DIR"
  base=$(basename -- "$agent")
  dest="$AGENTS_DIR/$base"
  if [ -L "$dest" ]; then
    existing=$(readlink -- "$dest" || true)
    case "$existing" in
      "$CACHE_DIR"/*|"$SRC"/*) run rm -- "$dest" ;;
      *)
        backup="$dest.backup.$(date +%Y%m%d%H%M%S)"
        warn "  existing $base is a link this installer did not create ($existing) -> moving to $(basename -- "$backup")"
        run mv -- "$dest" "$backup" ;;
    esac
  elif [ -e "$dest" ]; then
    backup="$dest.backup.$(date +%Y%m%d%H%M%S)"
    warn "  existing $base was not installed by this script -> moving to $(basename -- "$backup")"
    run mv -- "$dest" "$backup"
  fi
  if [ "$MODE" = link ]; then run ln -s -- "$agent" "$dest"; else run cp -- "$agent" "$dest"; fi
  agents=$((agents + 1))
done
[ "$agents" -eq 0 ] || done_msg "installed $agents agent(s) into $AGENTS_DIR"

# --- Codex ------------------------------------------------------------------
# Same directory, second host. `auto` installs only when a Codex home already exists, because
# creating ~/.codex for someone who does not run Codex is litter; `--codex` says do it anyway.
codex_wanted() {
  case "$CODEX" in
    no)  return 1 ;;
    yes) return 0 ;;
    *)   [ -d "$CODEX_DIR" ] ;;
  esac
}

codex=0
if codex_wanted; then
  run mkdir -p "$CODEX_SKILLS_DIR"
  for skill in "$SRC"/*/skills/*/; do
    skill=${skill%/}
    [ -f "$skill/SKILL.md" ] || continue
    name=$(basename -- "$skill")
    clear_destination "$CODEX_SKILLS_DIR/$name" "$name (codex)"
    place_skill "$skill" "$CODEX_SKILLS_DIR/$name" "$name (codex)"
    codex=$((codex + 1))
  done
  done_msg "installed $codex skill(s) into $CODEX_SKILLS_DIR"
  # Not a caveat about the install — a caveat about the RUN. Codex has no subagent files, so the
  # dimensions cannot fan out there and SKILL.md's serial fallback is the path taken. Saying it
  # here is cheaper than a user concluding the skill is broken because no agents appeared.
  say "    note: Codex has no subagents; /codegraph runs its dimensions serially there"
elif [ "$CODEX" = auto ] && [ -n "${CODEX_HOME:-}" ]; then
  warn "note: CODEX_HOME is set to $CODEX_DIR but it does not exist; pass --codex to create it"
fi

say ""
done_msg "installed $installed skill(s) into $SKILLS_DIR"
[ "$DRY_RUN" -eq 0 ] || say "dry run: nothing was changed"
say "Verify with:  bash install.sh --list"
say "In Claude Code, run /doctor or list skills to confirm they are picked up."
if [ "$MODE" = link ]; then
  say "Update with:   bash install.sh --update"
else
  say "Update with:   bash install.sh --copy --update"
fi
