#!/usr/bin/env bash
# Movian SDK shim reachability — shared by install.sh and `mdev doctor`.
#
# Contract (movian-plugin-sdk#35, #38): ONE check, two callers. The installer
# asks at the moment the shims are placed; `mdev doctor` asks again later, after
# the user has changed something. Written twice they would drift, and every one
# of the four properties below fails SILENTLY -- producing a confident wrong
# answer rather than an error -- so drift would not be visible.
#
#   1. The bindir is scrubbed from PATH before probing. Otherwise the probe
#      inherits the entry from the caller's own shell and reports success in
#      BOTH directions. This is the defect in the check it replaces
#      (movian-plugin-sdk#34): it tested `:$PATH:` of the shell running the
#      installer, which is never the shell that will run mdev.
#   2. stdin comes from /dev/null. A ~/.bashrc that reads input hangs an
#      interactive probe indefinitely -- measured surviving a plain `timeout`.
#   3. The timeout kills with SIGKILL. Interactive bash does not reliably die on
#      SIGTERM, so `timeout` without `-s KILL` can return while the shell lives.
#   4. Callers assert on the verdict, never on output text. A probe still
#      sources the host's /etc/bash.bashrc, whose chatter belongs to the machine
#      rather than to the answer.
#
# Three outcomes, never a gate. Reachability is a property of the user's shell
# configuration, not a failure of the installation -- the files did get
# installed. Same ruling as the locator's: a command, not a gate (#3).

MOVIAN_SDK_CONFIG="${MOVIAN_SDK_CONFIG:-$HOME/.config/movian-sdk/config.json}"

# `movian_sdk_shquote` belongs to locate.sh, which every caller of this file
# already sources. Defined here only so sourcing this file alone -- as the
# selftest does -- is not a landmine.
if ! declare -F movian_sdk_shquote >/dev/null 2>&1; then
  movian_sdk_shquote() { printf '%q' "$1"; }
fi

# The block install.sh --fix-path writes. Delimited, so it is found by MARKER
# and never by line number: a real ~/.bashrc carries other tools' blocks, and
# this machine's already did (Devin's, and the Antigravity installer's bare
# unremovable line -- the counter-example this format exists to avoid).
MOVIAN_SDK_BLOCK_BEGIN="# >>> BEGIN MOVIAN SDK PATH >>>"
MOVIAN_SDK_BLOCK_END="# <<< END MOVIAN SDK PATH <<<"

# Debian's interactive guard, verbatim from /etc/skel/.bashrc, byte-identical
# across Debian 9-13 and Ubuntu 18.04-24.04. The block must go ABOVE it: below,
# the `return` fires first for `ssh host 'mdev ...'`, whose stdin is a socket, so
# bash reads ~/.bashrc and then leaves before reaching an appended line.
MOVIAN_SDK_GUARD_ANCHOR="# If not running interactively, don't do anything"


# Where the shims were installed. Recorded rather than guessed: bindir used to
# exist only as a local in install.sh, so any ${MOVIAN_SDK_BINDIR:-...} fallback
# was a convention that failed silently on a custom bindir -- that variable
# lives in the installer's shell and is never exported into an agent's.
movian_sdk_bindir() {
  if [ -n "${MOVIAN_SDK_BINDIR:-}" ]; then
    printf '%s\n' "$MOVIAN_SDK_BINDIR"
    return 0
  fi
  if [ -f "$MOVIAN_SDK_CONFIG" ]; then
    local bin
    bin="$(jq -r '.bin // empty' "$MOVIAN_SDK_CONFIG" 2>/dev/null)"
    if [ -n "$bin" ]; then
      printf '%s\n' "$bin"
      return 0
    fi
  fi
  return 1
}


# PATH with one entry removed. Pure bash: no dependency, and no surprise from a
# path containing whitespace.
movian_sdk_path_without() {
  local drop="$1" out="" p
  local IFS=:
  for p in $PATH; do
    [ "$p" = "$drop" ] && continue
    out="${out:+$out:}$p"
  done
  printf '%s\n' "$out"
}


# Ask ONE shell shape whether it reaches the shim at "$bindir".
# Prints REACHABLE / UNREACHABLE / UNDETERMINED. Always returns 0: the verdict
# is the output, so a caller under `set -e` is never aborted by an answer.
movian_sdk_probe() {
  local bindir="$1" shape="$2" flag rc=0
  case "$shape" in
    login)          flag=-lc ;;
    interactive)    flag=-ic ;;
    noninteractive) flag=-c  ;;
    *) printf 'UNDETERMINED\n'; return 0 ;;
  esac

  # The comparison, not merely `command -v`: another mdev earlier on PATH would
  # otherwise be reported as this installation being reachable.
  env -u BASH_ENV -u ENV \
      PATH="$(movian_sdk_path_without "$bindir")" \
      MOVIAN_SDK_EXPECT="$bindir/mdev" TERM=dumb \
      timeout -s KILL "${MOVIAN_SDK_PROBE_TIMEOUT:-6}" \
      bash "$flag" '[ "$(command -v mdev)" = "$MOVIAN_SDK_EXPECT" ]' \
      </dev/null >/dev/null 2>&1 || rc=$?

  case "$rc" in
    0)        printf 'REACHABLE\n' ;;
    124|137)  printf 'UNDETERMINED\n' ;;
    *)        printf 'UNREACHABLE\n' ;;
  esac
  return 0
}


# The three shapes a dotfile can serve. The agent's own `bash -c` is deliberately
# absent: it reads neither ~/.profile nor ~/.bashrc, so no environment mechanism
# can close it and none is claimed here. It is served SDK-side instead, by the
# resolution preamble the skills carry (#41).
# Sets MOVIAN_SDK_REACH_WORST to the worst verdict seen. Always returns 0: a
# verdict is data, not a failure, and install.sh runs under `set -e`.
movian_sdk_reachability_report() {
  local bindir="$1" shape verdict
  MOVIAN_SDK_REACH_WORST=REACHABLE
  for shape in login interactive; do
    verdict="$(movian_sdk_probe "$bindir" "$shape")"
    printf 'reachable: %-14s %s\n' "$shape" "$verdict"
    case "$verdict" in
      UNREACHABLE)  MOVIAN_SDK_REACH_WORST=UNREACHABLE ;;
      UNDETERMINED) [ "$MOVIAN_SDK_REACH_WORST" = REACHABLE ] &&
                      MOVIAN_SDK_REACH_WORST=UNDETERMINED ;;
    esac
  done
  return 0
}


# One line per outcome, with a fix that can be pasted and RUN -- the discipline
# lib/locate.sh already keeps, and which the selftest exercises by running it.
# "Insert three lines above the guard in your ~/.bashrc" is a description; a
# test cannot run it and a reader gets it wrong.
movian_sdk_explain_unreachable() {
  local bindir="$1" root="${2:-}" verdict="$3"
  if [ "$verdict" = UNDETERMINED ]; then
    echo "warning: could not determine whether $(movian_sdk_shquote "$bindir") is reachable" >&2
    echo "  a shell startup file did not finish within ${MOVIAN_SDK_PROBE_TIMEOUT:-6}s." >&2
    echo "  this is not a verdict either way -- rerun, or check your ~/.bashrc." >&2
    return 0
  fi
  echo "warning: $(movian_sdk_shquote "$bindir") is not reachable from the shells that will run mdev" >&2
  echo "  your ~/.profile puts it on PATH for LOGIN shells only; Debian's ~/.bashrc does not," >&2
  echo "  so an ordinary terminal answers 'mdev: command not found'." >&2
  if [ -n "$root" ]; then
    echo "  fix: $(movian_sdk_shquote "$root")/install.sh --fix-path" >&2
  else
    echo "  fix: rerun this repository's ./install.sh --fix-path" >&2
  fi
}


# --- the managed block -----------------------------------------------------

movian_sdk_block_text() {
  local bindir="$1"
  # Guarded on MEMBERSHIP, not on the directory existing. Debian's own stanza
  # guards on existence, which re-prepends in every nested shell: measured 1, 2,
  # 3 entries at nesting depth 1, 2, 3. Above the interactive guard that stanza
  # would run in more shells still, so its form cannot be reused here.
  cat <<EOF
$MOVIAN_SDK_BLOCK_BEGIN
if [[ ":\$PATH:" != *":$bindir:"* ]]; then
  PATH="$bindir:\$PATH"
fi
$MOVIAN_SDK_BLOCK_END

EOF
}


# Strip the block from stdin. Exact inverse of insertion, INCLUDING the single
# blank line written after END -- dropping only the body leaves the file one
# line longer on every apply/remove cycle. The prototype (#40) caught that.
movian_sdk_block_strip() {
  awk -v b="$MOVIAN_SDK_BLOCK_BEGIN" -v e="$MOVIAN_SDK_BLOCK_END" '
    $0 == b { inblock = 1; next }
    $0 == e { inblock = 0; eat = 1; next }
    inblock { next }
    eat     { eat = 0; if ($0 == "") next }
    { print }
  '
}


# Write, rewrite, or remove the block in "$rc_file". mode: apply | remove.
# Idempotent IN THE FILE. It cannot be idempotent in $PATH: a login shell ends
# up with the entry twice because Debian's ~/.profile SOURCES ~/.bashrc and then
# prepends its own UNGUARDED line, which runs after ours. No guard written here
# can prevent that, so #34's "idempotent" has to be read as in-the-file.
movian_sdk_fix_path() {
  local rc_file="$1" bindir="$2" mode="${3:-apply}" tmp stripped
  [ -f "$rc_file" ] || { echo "error: $(movian_sdk_shquote "$rc_file") does not exist" >&2; return 1; }

  stripped="$(movian_sdk_block_strip < "$rc_file")"

  if [ "$mode" = remove ]; then
    if ! grep -qxF "$MOVIAN_SDK_BLOCK_BEGIN" "$rc_file"; then
      echo "  no Movian SDK block in $rc_file -- nothing to remove"
      return 0
    fi
    printf '%s\n' "$stripped" > "$rc_file"
    echo "  removed the Movian SDK block from $rc_file"
    return 0
  fi

  # Refuse rather than guess. Appending at EOF would satisfy the interactive
  # shape and silently leave `ssh host 'mdev ...'` broken -- a partial fix
  # reported as a complete one, which is the defect class #34 was filed about.
  if ! printf '%s\n' "$stripped" | grep -qxF "$MOVIAN_SDK_GUARD_ANCHOR"; then
    echo "error: no interactive guard found in $(movian_sdk_shquote "$rc_file")" >&2
    echo "  expected the line: $MOVIAN_SDK_GUARD_ANCHOR" >&2
    echo "  this file is not shaped like Debian's /etc/skel/.bashrc, and inserting" >&2
    echo "  below the guard would leave ssh unfixed while reporting success." >&2
    echo "  fix: add these lines yourself, ABOVE whatever returns for non-interactive shells:" >&2
    movian_sdk_block_text "$bindir" | sed 's/^/    /' >&2
    return 1
  fi

  tmp="$(mktemp)"
  # The blank line is emitted here rather than carried in block_text: `$( )`
  # strips trailing newlines, so a separator baked into the heredoc is lost and
  # the block ends up butted against the guard. block_strip eats exactly one
  # blank after END, so emitting it here keeps removal an exact inverse.
  printf '%s\n' "$stripped" | awk -v anchor="$MOVIAN_SDK_GUARD_ANCHOR" -v block="$(movian_sdk_block_text "$bindir")" '
    !done && $0 == anchor { printf "%s\n\n", block; done = 1 }
    { print }
  ' > "$tmp"
  cat "$tmp" > "$rc_file"
  rm -f "$tmp"
  echo "  wrote the Movian SDK block into $rc_file (above the interactive guard)"
}
