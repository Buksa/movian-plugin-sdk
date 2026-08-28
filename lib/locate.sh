#!/usr/bin/env bash
# Movian SDK core locator — shared by the ~/.local/bin/mdev and movian-lsp shims.
#
# Contract (movian-plugin-sdk#3): one designated core, resolved as
#   MOVIAN_CORE -> ~/.config/movian-sdk/config.json -> hard fail.
# There is deliberately no search fallback: more than one built checkout exists
# on this machine and Orca keeps creating more, so a heuristic would guess.
#
# Validation is PRESENCE, not freshness. Plugin work edits JS and never
# invalidates the core C build, so a staleness gate would fire constantly and
# train agents to ignore it. Use `mdev doctor` to see freshness on demand.

MOVIAN_SDK_CONFIG="${MOVIAN_SDK_CONFIG:-$HOME/.config/movian-sdk/config.json}"

# Paths are printed inside commands the reader is meant to paste, and a path
# may contain a quote: `/tmp/core's-copy` inside `cd '...'` yields a command
# that will not run. `printf %q` is bash's own escaping, and it leaves an
# ordinary path unadorned.
movian_sdk_shquote() {
  printf '%q' "$1"
}


# Git reads the repository to work on from the environment before it looks at
# `-C`, so `GIT_DIR` exported by a hook or a wrapping tool silently redirects
# these probes at the CALLER's repository. Measured: under `GIT_DIR=<sdk>/.git`,
# `git -C <target> cat-file -e HEAD:lib/locate.sh` succeeds, and that file
# exists only in the SDK. `git rev-parse --local-env-vars` is git's own list of
# the variables that do this. Measured on git 2.43: that list is 15 names
# and `GIT_CEILING_DIRECTORIES` is NOT among them, so clearing it here
# cannot take the caller's sandbox bound with it. `locate_selftest.py`
# pins that premise rather than guarding against it: a guard no test can
# exercise is worse than an assumption something checks.
movian_sdk_git() {
  local root="$1"
  shift
  (
    unset $(git rev-parse --local-env-vars 2>/dev/null) 2>/dev/null || true
    # Classification reads git's own words, so they must not be translated.
    LC_ALL=C LANGUAGE= git -C "$root" "$@"
  )
}


# Why `support/devtools/mdev` is absent. Three causes, and only one of them is
# "you pointed at the wrong kind of directory" -- which is what this used to
# say about all three. A designated core sitting on a revision that predates
# the devtools is the case actually met in practice (movian-plugin-sdk#32): a
# real clone of the project, `.git` present, `support/devtools/` present, only
# `mdev` itself missing because the branch is old. The cause is the revision,
# and the advice to check whether it is a Movian checkout at all sends the
# reader past it.
#
# Decided on evidence already at hand and free: whether git calls it a work
# tree, and where that tree's root is.
movian_sdk_explain_missing_mdev() {
  local root="$1" top head branch

  if ! command -v git >/dev/null 2>&1; then
    echo "  fix: point at a Movian checkout, not an unrelated directory." >&2
    return
  fi

  # "git said no" and "git could not answer" are different findings. A
  # checkout owned by another UID -- a host-mounted tree in a container is
  # the ordinary way that happens -- makes every probe fail with dubious
  # ownership, and reporting that as "not a Movian checkout" is the exact
  # conflation this function exists to remove. Git's own message is the
  # useful thing to show; it already names the remedy.
  # stderr goes to a file rather than into the answer: `GIT_TRACE=1` makes a
  # SUCCESSFUL rev-parse write to stderr too, and merging the two put a trace
  # line inside `$top` -- the message then offered a timestamp as the path to
  # point at.
  local errfile status
  errfile="$(mktemp)"
  top="$(movian_sdk_git "$root" rev-parse --show-toplevel 2>"$errfile")"
  status=$?
  if [ $status -ne 0 ]; then
    local probe
    probe="$(cat "$errfile")"
    rm -f "$errfile"
    # "git said no" and "git could not answer" are different findings, and
    # the difference is read from a C-locale message: `movian_sdk_git` forces
    # LC_ALL=C so this comparison is not against a translation.
    case "$probe" in
      *"not a git repository"*)
        echo "  fix: point at a Movian checkout, not an unrelated directory." >&2
        ;;
      *)
        echo "  git could not read it, so nothing further could be" >&2
        echo "  determined about the path:" >&2
        printf '%s\n' "$probe" | while IFS= read -r line; do
          printf '    %s\n' "$line" >&2
        done
        ;;
    esac
    return
  fi
  rm -f "$errfile"

  # Being a git work tree is not evidence of being THIS project, and plenty of
  # unrelated directories are version-controlled. Nor is `src/main.c`, which
  # any C project may have -- accepting either marker alone called a bare C
  # repository a Movian checkout on an old revision.
  #
  # Both of these together are specific: `configure.inc` is this build system
  # and `prop.h` is this property system, and no unrelated project carries the
  # pair. Verified present in HEAD of both the oldest branch here (M7-272) and
  # movian6. A revision so old it lacks them falls back to the
  # unrelated-directory message, which is the conservative direction.
  if ! movian_sdk_git "$root" cat-file -e HEAD:support/configure.inc 2>/dev/null ||
     ! movian_sdk_git "$root" cat-file -e HEAD:src/prop/prop.h 2>/dev/null; then
    echo "  it is a git checkout, but not of Movian -- HEAD has no" >&2
    echo "  support/configure.inc + src/prop/prop.h." >&2
    echo "  fix: point at a Movian checkout, not an unrelated directory." >&2
    return
  fi

  # `git -C` answers for the enclosing tree, so a path INSIDE a checkout
  # resolves happily and is a different mistake with a different fix.
  if [ "$top" != "$(cd "$root" && pwd -P)" ]; then
    echo "  that path is inside the Movian checkout at '$top', not its root." >&2
    echo "  fix: point at $(movian_sdk_shquote "$top")." >&2
    return
  fi

  # The revision is only to blame when the revision really lacks it. A sparse
  # checkout, or a deleted file, leaves HEAD carrying `mdev` while the working
  # tree does not -- and "update this checkout" would do nothing at all.
  if movian_sdk_git "$root" cat-file -e HEAD:support/devtools/mdev 2>/dev/null; then
    echo "  this revision DOES carry it -- the working-tree copy is missing." >&2
    # Three ways the file goes missing, and only one command restores all
    # three. Without `HEAD` the pathspec is read from the INDEX, where a
    # `git rm --cached` has already removed it; without the flag a
    # sparse-checkout exclusion refuses the pathspec. Measured, all three:
    #
    #   git checkout HEAD --ignore-skip-worktree-bits --   deleted/staged/sparse: ok
    #   git checkout HEAD --                               sparse: FAIL
    #   git checkout --ignore-skip-worktree-bits --        staged: FAIL
    # `git checkout HEAD -- <path>` rewrites the INDEX as well, so a staged
    # modification of `mdev` would be replaced by the committed version
    # without a word. Restoring from the index keeps it; only a staged
    # DELETION -- where the index no longer has the path -- needs HEAD.
    local source=""
    movian_sdk_git "$root" cat-file -e :support/devtools/mdev 2>/dev/null ||
      source="HEAD "
    echo "  fix: cd $(movian_sdk_shquote "$root") && git checkout ${source}\\" >&2
    echo "       --ignore-skip-worktree-bits -- support/devtools/mdev" >&2
    echo "  (if support/ is excluded by sparse-checkout, widen the patterns" >&2
    echo "   too, or the next checkout drops it again.)" >&2
    return
  fi

  head="$(movian_sdk_git "$root" rev-parse --short HEAD 2>/dev/null)" || head="an unborn HEAD"
  branch="$(movian_sdk_git "$root" rev-parse --abbrev-ref HEAD 2>/dev/null)" || branch="HEAD"
  echo "  it IS a Movian checkout -- on $branch @ $head, a revision without it." >&2
  echo "  fix: update this checkout, or point at one whose revision has support/devtools/mdev." >&2
}


# Sets MOVIAN_SDK_CORE and MOVIAN_SDK_CORE_SOURCE. Returns non-zero on failure
# with a diagnosis on stderr.
movian_sdk_locate() {
  local root="" source=""

  if [ -n "${MOVIAN_CORE:-}" ]; then
    root="$MOVIAN_CORE"
    source="MOVIAN_CORE"
  elif [ -f "$MOVIAN_SDK_CONFIG" ]; then
    root="$(jq -r '.core // empty' "$MOVIAN_SDK_CONFIG" 2>/dev/null)"
    source="$MOVIAN_SDK_CONFIG"
    if [ -z "$root" ]; then
      echo "movian-sdk: '$MOVIAN_SDK_CONFIG' has no usable \"core\" key." >&2
      echo "  fix: write {\"core\": \"/abs/path/to/movian/checkout\"} into it." >&2
      return 1
    fi
  else
    echo "movian-sdk: no Movian core configured." >&2
    echo "  fix: create $MOVIAN_SDK_CONFIG containing" >&2
    echo "       {\"core\": \"/abs/path/to/movian/checkout\"}" >&2
    echo "       or set MOVIAN_CORE for this session only." >&2
    return 1
  fi

  if [ ! -d "$root" ]; then
    echo "movian-sdk: core '$root' (from $source) is not a directory." >&2
    echo "  fix: correct the path, or clone the core there." >&2
    return 1
  fi
  if [ ! -e "$root/support/devtools/mdev" ]; then
    echo "movian-sdk: core '$root' (from $source) has no support/devtools/mdev." >&2
    movian_sdk_explain_missing_mdev "$root"
    return 1
  fi
  if [ ! -x "$root/build.debug/movian" ]; then
    echo "movian-sdk: core '$root' (from $source) has no executable build.debug/movian." >&2
    echo "  fix: cd $(movian_sdk_shquote "$root") && ./support/configure-linux-debug.sh && make BUILD=debug -j\$(nproc)" >&2
    echo "  note: run configure ONLY from the checkout that owns its build.debug." >&2
    return 1
  fi

  MOVIAN_SDK_CORE="$root"
  MOVIAN_SDK_CORE_SOURCE="$source"
  return 0
}
