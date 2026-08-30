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
# One spelling for one directory. Without this a trailing slash produced a
# CONFIDENTLY WRONG answer on a working install: `~/.local/bin` probed
# REACHABLE while `~/.local/bin/` probed UNREACHABLE, because the scrub and the
# `$bindir/mdev` comparison are both textual. `mdev doctor` reported a permanent
# MISMATCH for the same reason.
#
# Relative paths are REFUSED rather than normalised against the caller's cwd.
# `--fix-path` writes this string into ~/.bashrc, and a relative entry there
# lands at the FRONT of PATH in every shell, resolving against whatever
# directory the user happens to be in -- so `./mybin/git` in any checked-out
# repository would run instead of git. install.sh already demands an absolute
# path for the core; the bindir is the more dangerous of the two and demanded
# none.
movian_sdk_normalise_bindir() {
  local dir="$1"
  case "$dir" in
    "") echo "error: empty bindir" >&2; return 1 ;;
    # PATH is colon-separated, so a directory containing a colon cannot be
    # represented in it at all -- neither the scrub nor the membership guard the
    # block writes could tell it from two shorter entries. Refuse rather than
    # write something that silently means something else.
    *:*) echo "error: bindir must not contain ':', which separates PATH entries" >&2
         echo "  got $(movian_sdk_shquote "$dir")" >&2
         return 1 ;;
    /*) ;;
    *)  echo "error: bindir must be an absolute path, got $(movian_sdk_shquote "$dir")" >&2
        echo "  a relative directory written into ~/.bashrc lands at the front of PATH" >&2
        echo "  in every shell and resolves against the current directory." >&2
        return 1 ;;
  esac
  # Collapse repeated slashes and drop every trailing one, but never reduce the
  # root itself to the empty string.
  while :; do
    case "$dir" in
      *//*) dir="${dir//\/\//\/}" ;;
      *)    break ;;
    esac
  done
  while [ "${dir%/}" != "$dir" ] && [ "$dir" != "/" ]; do dir="${dir%/}"; done
  printf '%s\n' "$dir"
}


# Where the shims were installed. Recorded rather than guessed: bindir used to
# exist only as a local in install.sh, so any ${MOVIAN_SDK_BINDIR:-...} fallback
# was a convention that failed silently on a custom bindir -- that variable
# lives in the installer's shell and is never exported into an agent's.
#
# The recorded value wins over the environment. MOVIAN_SDK_BINDIR is the
# installer's own override and is never exported into an agent session, so
# preferring it blinded `mdev doctor` in both directions: a stale `bin` key that
# breaks every agent reported clean, and a developer with the variable set got a
# spurious MISMATCH. The config is what agents actually read, so the config is
# what gets checked.
movian_sdk_bindir() {
  local bin=""
  if [ -f "$MOVIAN_SDK_CONFIG" ]; then
    bin="$(jq -r '.bin // empty' "$MOVIAN_SDK_CONFIG" 2>/dev/null)" || bin=""
  fi
  [ -n "$bin" ] || bin="${MOVIAN_SDK_BINDIR:-}"
  [ -n "$bin" ] || return 1
  movian_sdk_normalise_bindir "$bin" 2>/dev/null || printf '%s\n' "$bin"
}


# PATH with one entry removed. Pure bash: no dependency, and no surprise from a
# path containing whitespace.
movian_sdk_path_without() {
  local drop="$1" out="" p
  local IFS=:
  # `set -f` for the loop only: an unquoted expansion of $PATH is subject to
  # pathname expansion, so a PATH entry containing `*` or `?` would be replaced
  # by matching filenames -- silently rewriting the PATH the probe then runs
  # under. IFS splitting is what this loop wants; globbing is not.
  local reglob=0
  case "$-" in *f*) ;; *) reglob=1; set -f ;; esac
  for p in $PATH; do
    [ "$p" = "$drop" ] && continue
    out="${out:+$out:}$p"
  done
  [ "$reglob" -eq 0 ] || set +f
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

  # Resolve the tools BEFORE scrubbing. `env` finds `timeout` and `timeout`
  # finds `bash` along the probe's own PATH, so when the bindir is the only
  # entry the scrub leaves nothing to run and the shell never starts -- which
  # was then printed as UNREACHABLE, a confident answer about a measurement that
  # never happened. Absolute paths take the search out of the probe entirely.
  local bash_bin timeout_bin
  bash_bin="$(command -v bash 2>/dev/null)" || bash_bin=""
  timeout_bin="$(command -v timeout 2>/dev/null)" || timeout_bin=""
  if [ -z "$bash_bin" ] || [ -z "$timeout_bin" ]; then
    # No GNU timeout (BSD, busybox) or no bash: this host cannot be measured
    # the way the contract requires. That is undetermined, not unreachable.
    printf 'UNDETERMINED\n'
    return 0
  fi

  # The comparison, not merely `command -v`: another mdev earlier on PATH would
  # otherwise be reported as this installation being reachable.
  env -u BASH_ENV -u ENV \
      PATH="$(movian_sdk_path_without "$bindir")" \
      MOVIAN_SDK_EXPECT="$bindir/mdev" TERM=dumb \
      "$timeout_bin" -s KILL "${MOVIAN_SDK_PROBE_TIMEOUT:-6}" \
      "$bash_bin" "$flag" '[ "$(command -v mdev)" = "$MOVIAN_SDK_EXPECT" ]' \
      </dev/null >/dev/null 2>&1 || rc=$?

  case "$rc" in
    0)        printf 'REACHABLE\n' ;;
    # 124 = timeout fired, 137 = SIGKILL landed: measured, and it hung.
    124|137)  printf 'UNDETERMINED\n' ;;
    # 125 timeout itself failed, 126 found but not executable, 127 not found.
    # None of these are a verdict about the bindir -- the probe never ran.
    125|126|127) printf 'UNDETERMINED\n' ;;
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
# Sets MOVIAN_SDK_REACH_WORST to the worst verdict seen, and
# MOVIAN_SDK_REACH_<SHAPE> to each shape's own. The per-shape verdicts are kept
# because the remedy differs: a login shell that cannot reach the bindir is not
# repaired by editing ~/.bashrc, so a diagnosis that assumes which half failed
# can send the reader to the wrong file.
# Always returns 0: a verdict is data, not a failure, and install.sh runs under
# `set -e`.
movian_sdk_reachability_report() {
  local bindir="$1" shape verdict
  MOVIAN_SDK_REACH_WORST=REACHABLE
  MOVIAN_SDK_REACH_LOGIN=""
  MOVIAN_SDK_REACH_INTERACTIVE=""
  for shape in login interactive; do
    verdict="$(movian_sdk_probe "$bindir" "$shape")"
    printf 'reachable: %-14s %s\n' "$shape" "$verdict"
    case "$shape" in
      login)       MOVIAN_SDK_REACH_LOGIN="$verdict" ;;
      interactive) MOVIAN_SDK_REACH_INTERACTIVE="$verdict" ;;
    esac
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
  local login="${MOVIAN_SDK_REACH_LOGIN:-}" inter="${MOVIAN_SDK_REACH_INTERACTIVE:-}"
  echo "warning: $(movian_sdk_shquote "$bindir") is not reachable from every shell that will run mdev" >&2

  # Called without a preceding report, the per-shape variables are empty. Empty
  # is not "unreachable" -- it is "nothing was measured" -- and treating it as a
  # verdict produced a confident diagnosis from no data at all.
  if [ -z "$login" ] && [ -z "$inter" ]; then
    echo "  no per-shape measurement is available, so which shell fails is not stated." >&2
    echo "  run movian_sdk_reachability_report first, or use \`mdev doctor\`." >&2
    if [ -n "$root" ]; then
      echo "  fix: $(movian_sdk_shquote "$root")/install.sh --fix-path" >&2
    else
      echo "  fix: rerun this repository's ./install.sh --fix-path" >&2
    fi
    return 0
  fi

  # An UNDETERMINED shape was never measured, so nothing may be asserted about
  # it. Saying "a login shell finds it" when the login probe was killed states
  # a fact that was not established -- the same class of confident wrong answer
  # this whole check exists to remove.
  if [ "$login" = UNDETERMINED ] || [ "$inter" = UNDETERMINED ]; then
    [ "$login" = UNDETERMINED ] &&
      echo "  the LOGIN shape could not be measured; no claim is made about it." >&2
    [ "$inter" = UNDETERMINED ] &&
      echo "  the ORDINARY TERMINAL shape could not be measured; no claim is made about it." >&2
    if [ "$login" = UNREACHABLE ] || [ "$inter" = UNREACHABLE ]; then
      echo "  of the shapes that WERE measured, at least one cannot find it." >&2
    fi
    if [ -n "$root" ]; then
      echo "  fix: $(movian_sdk_shquote "$root")/install.sh --fix-path" >&2
    else
      echo "  fix: rerun this repository's ./install.sh --fix-path" >&2
    fi
    return 0
  fi

  # Name the shape that actually failed. Claiming "login works, terminals do
  # not" unconditionally is false whenever a custom bindir is in neither startup
  # file, and exactly backwards when login is the failing half -- and there the
  # ~/.bashrc edit below would not repair it at all.
  if [ "$login" != REACHABLE ] && [ "$inter" != REACHABLE ]; then
    echo "  NEITHER a login shell nor an ordinary terminal can find it, so no startup" >&2
    echo "  file puts it on PATH. That is the expected state for a bindir outside" >&2
    echo "  ~/.local/bin, which Debian's ~/.profile is the only thing that adds." >&2
  elif [ "$inter" != REACHABLE ]; then
    echo "  a login shell finds it and an ordinary terminal does not: ~/.profile adds it," >&2
    echo "  Debian's ~/.bashrc does not, and only login shells read ~/.profile." >&2
  else
    echo "  an ordinary terminal finds it and a LOGIN shell does not. The remedy below" >&2
    echo "  writes to ~/.bashrc, which login shells reach only because Debian's" >&2
    echo "  ~/.profile sources it -- so if yours does not, or you have a ~/.bash_profile" >&2
    echo "  shadowing ~/.profile, fix that file instead." >&2
  fi

  if [ -n "$root" ]; then
    echo "  fix: $(movian_sdk_shquote "$root")/install.sh --fix-path" >&2
  else
    echo "  fix: rerun this repository's ./install.sh --fix-path" >&2
  fi
}


# --- the managed block -----------------------------------------------------

movian_sdk_block_text() {
  local bindir="$1" quoted
  # The path is written as shell DATA, never interpolated into shell code. A
  # bindir is user-supplied via MOVIAN_SDK_BINDIR, and a component like
  # `$(touch /tmp/pwned)` would otherwise be substituted on every interactive
  # shell start -- verified doing exactly that before this was quoted. Glob
  # characters mattered too: unquoted in the `[[` pattern they would change the
  # membership test rather than be compared literally.
  quoted="$(printf '%q' "$bindir")"
  # Guarded on MEMBERSHIP, not on the directory existing. Debian's own stanza
  # guards on existence, which re-prepends in every nested shell: measured 1, 2,
  # 3 entries at nesting depth 1, 2, 3. Above the interactive guard that stanza
  # would run in more shells still, so its form cannot be reused here.
  cat <<EOF
$MOVIAN_SDK_BLOCK_BEGIN
movian_sdk_bin=$quoted
if [[ ":\$PATH:" != *":\$movian_sdk_bin:"* ]]; then
  PATH="\$movian_sdk_bin:\$PATH"
fi
unset movian_sdk_bin
$MOVIAN_SDK_BLOCK_END

EOF
}


# Are the markers a complete, ordered pair? Returns 0 for a well-formed file
# (zero or one intact block), 1 otherwise.
#
# This is a guard against DESTROYING the file. If a user deleted the END marker,
# a naive strip treats everything after BEGIN as block body and discards it: on
# a stock ~/.bashrc that is 117 lines in and 3 lines out, silently, from a
# command whose entire job is to remove five lines.
movian_sdk_block_wellformed() {
  # Trailing whitespace on a marker is an editor artefact, not damage. Matching
  # it exactly made an otherwise intact block look half-open and refused every
  # edit -- a false positive on the one check whose job is to prevent data loss.
  awk -v b="$MOVIAN_SDK_BLOCK_BEGIN" -v e="$MOVIAN_SDK_BLOCK_END" '
    { line = $0; sub(/[ \t]+$/, "", line) }
    line == b { if (open) { bad = 1 } ; open = 1; nb++ ; next }
    line == e { if (!open) { bad = 1 } ; open = 0; ne++ ; next }
    END { exit (bad || open || nb > 1 || nb != ne) ? 1 : 0 }
  ' "$1"
}


# Is a managed block present? Tolerant of trailing whitespace, like the
# well-formedness check.
movian_sdk_has_block() {
  awk -v b="$MOVIAN_SDK_BLOCK_BEGIN" '
    { line = $0; sub(/[ \t]+$/, "", line) }
    line == b { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$1"
}


# Strip the block from a file. Exact inverse of insertion, INCLUDING the single
# blank line written after END -- dropping only the body leaves the file one
# line longer on every apply/remove cycle. The prototype (#40) caught that.
#
# Callers must have passed movian_sdk_block_wellformed first; this assumes it.
movian_sdk_block_strip() {
  awk -v b="$MOVIAN_SDK_BLOCK_BEGIN" -v e="$MOVIAN_SDK_BLOCK_END" '
    { line = $0; sub(/[ \t]+$/, "", line) }
    line == b { inblock = 1; next }
    line == e { inblock = 0; eat = 1; next }
    inblock { next }
    eat     { eat = 0; if ($0 == "") next }
    { print }
  ' "$1"
}


# Write, rewrite, or remove the block in "$rc_file". mode: apply | remove.
# Idempotent IN THE FILE. It cannot be idempotent in $PATH: a login shell ends
# up with the entry twice because Debian's ~/.profile SOURCES ~/.bashrc and then
# prepends its own UNGUARDED line, which runs after ours. No guard written here
# can prevent that, so #34's "idempotent" has to be read as in-the-file.
movian_sdk_fix_path() {
  local rc_file="$1" bindir="$2" mode="${3:-apply}" tmp stripped backup
  [ -f "$rc_file" ] || { echo "error: $(movian_sdk_shquote "$rc_file") does not exist" >&2; return 1; }

  # Refuse to touch a file whose markers are damaged, rather than interpret the
  # damage. Removing five lines must never be able to delete the file's tail.
  if ! movian_sdk_block_wellformed "$rc_file"; then
    echo "error: the Movian SDK markers in $(movian_sdk_shquote "$rc_file") are damaged" >&2
    echo "  expected at most one intact block, opened by" >&2
    echo "    $MOVIAN_SDK_BLOCK_BEGIN" >&2
    echo "  and closed by" >&2
    echo "    $MOVIAN_SDK_BLOCK_END" >&2
    echo "  refusing to edit: interpreting a half-open block would discard everything" >&2
    echo "  after it. fix: repair or delete the markers by hand, then rerun." >&2
    return 1
  fi

  stripped="$(movian_sdk_block_strip "$rc_file")"

  # Nothing to do is not a modification. Creating a backup here let a no-op
  # `--unfix-path` claim the single backup slot, so every LATER real edit
  # announced a backup that predated nothing.
  if [ "$mode" = remove ] && ! movian_sdk_has_block "$rc_file"; then
    echo "  no Movian SDK block in $rc_file -- nothing to remove"
    return 0
  fi

  # Back up before EVERY modification, not once ever. A single fixed name meant
  # the second run onwards was unprotected while still printing a backup path --
  # the reassurance outlived the thing it described. This is a file the user
  # owns; the SDK's discipline for files it merely installs is already "never
  # clobber silently" (install.sh install_file), which backs up per write.
  #
  # Deliberately NOT an atomic rename: ~/.bashrc is very often a symlink into a
  # dotfiles repository, and `mv` over it replaces the symlink with a regular
  # file -- verified. Redirection writes THROUGH the symlink and keeps such a
  # setup working, and the backup covers what atomicity was meant to protect.
  # Timestamps are second-granular, and an apply immediately followed by a
  # remove lands inside one second -- the second copy would overwrite the first
  # and the pre-apply original would be gone. Uniquify rather than clobber.
  backup="$rc_file.movian-sdk.bak-$(date +%Y%m%d%H%M%S)"
  if [ -e "$backup" ]; then
    local seq=2
    while [ -e "$backup.$seq" ]; do seq=$((seq + 1)); done
    backup="$backup.$seq"
  fi
  cp -p "$rc_file" "$backup"

  if [ "$mode" = remove ]; then
    printf '%s\n' "$stripped" > "$rc_file"
    echo "  removed the Movian SDK block from $rc_file (backup: $backup)"
    return 0
  fi

  # Refuse rather than guess. Appending at EOF would satisfy the interactive
  # shape and silently leave `ssh host 'mdev ...'` broken -- a partial fix
  # reported as a complete one, which is the defect class #34 was filed about.
  # A here-string, not a pipe. `grep -q` exits at the first match and closes the
  # pipe, so `printf` takes SIGPIPE; under `set -o pipefail` -- which install.sh
  # sets -- that made the whole pipeline fail and the anchor look MISSING. It
  # only showed up once the file was large enough for printf to still be writing
  # when grep left: an 89KiB ~/.bashrc refused the fix and aborted the install,
  # while a stock 3.5KiB one was fine.
  if ! grep -qxF "$MOVIAN_SDK_GUARD_ANCHOR" <<<"$stripped"; then
    echo "error: no interactive guard found in $(movian_sdk_shquote "$rc_file")" >&2
    echo "  expected the line: $MOVIAN_SDK_GUARD_ANCHOR" >&2
    echo "  this file is not shaped like Debian's /etc/skel/.bashrc, and inserting" >&2
    echo "  below the guard would leave ssh unfixed while reporting success." >&2
    echo "  fix: add these lines yourself, ABOVE whatever returns for non-interactive shells:" >&2
    movian_sdk_block_text "$bindir" | sed 's/^/    /' >&2
    return 1
  fi

  tmp="$(mktemp)"
  # Split at the anchor and splice, rather than passing the block through
  # `awk -v`. awk processes escape sequences in a -v assignment, so it UNDOES
  # the `printf %q` quoting of the bindir -- a path containing $(...) was
  # written back as live code and executed on every interactive shell start.
  # head/tail never reinterprets what it copies.
  local n
  # Same SIGPIPE hazard as the anchor test above: `grep -m1` and `head` both
  # stop early and would break the pipe under pipefail. Here-strings have no
  # writer to signal.
  n="$(grep -nxF -m1 "$MOVIAN_SDK_GUARD_ANCHOR" <<<"$stripped" | cut -d: -f1)"
  {
    head -n "$((n - 1))" <<<"$stripped"
    # The trailing blank line is emitted by block_text's heredoc; block_strip
    # eats exactly one blank after END, which keeps removal an exact inverse.
    movian_sdk_block_text "$bindir"
    tail -n "+$n" <<<"$stripped"
  } > "$tmp"
  cat "$tmp" > "$rc_file"
  rm -f "$tmp"
  echo "  wrote the Movian SDK block into $rc_file (above the interactive guard)"
}
