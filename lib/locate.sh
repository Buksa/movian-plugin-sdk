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

  if ! command -v git >/dev/null 2>&1 ||
     ! top="$(git -C "$root" rev-parse --show-toplevel 2>/dev/null)"; then
    echo "  fix: point at a Movian checkout, not an unrelated directory." >&2
    return
  fi

  # Being a git work tree is not evidence of being THIS project, and plenty of
  # unrelated directories are version-controlled. Without this the previously
  # correct "unrelated directory" verdict regressed into advice to update a
  # repository that was never Movian.
  if ! git -C "$root" cat-file -e HEAD:src/main.c 2>/dev/null &&
     ! git -C "$root" cat-file -e HEAD:support/configure.inc 2>/dev/null; then
    echo "  it is a git checkout, but not of Movian -- no src/main.c in HEAD." >&2
    echo "  fix: point at a Movian checkout, not an unrelated directory." >&2
    return
  fi

  # `git -C` answers for the enclosing tree, so a path INSIDE a checkout
  # resolves happily and is a different mistake with a different fix.
  if [ "$top" != "$(cd "$root" && pwd -P)" ]; then
    echo "  that path is inside the Movian checkout at '$top', not its root." >&2
    echo "  fix: point at '$top'." >&2
    return
  fi

  # The revision is only to blame when the revision really lacks it. A sparse
  # checkout, or a deleted file, leaves HEAD carrying `mdev` while the working
  # tree does not -- and "update this checkout" would do nothing at all.
  if git -C "$root" cat-file -e HEAD:support/devtools/mdev 2>/dev/null; then
    echo "  this revision DOES carry it -- the working-tree copy is missing." >&2
    echo "  fix: cd '$root' && git checkout -- support/devtools/mdev" >&2
    echo "  (a sparse checkout that excludes support/ produces this too.)" >&2
    return
  fi

  head="$(git -C "$root" rev-parse --short HEAD 2>/dev/null)" || head="an unborn HEAD"
  branch="$(git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null)" || branch="HEAD"
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
    echo "  fix: cd '$root' && ./support/configure-linux-debug.sh && make BUILD=debug -j\$(nproc)" >&2
    echo "  note: run configure ONLY from the checkout that owns its build.debug." >&2
    return 1
  fi

  MOVIAN_SDK_CORE="$root"
  MOVIAN_SDK_CORE_SOURCE="$source"
  return 0
}
