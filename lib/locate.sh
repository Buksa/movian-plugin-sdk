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
    echo "  fix: point at a Movian checkout, not an unrelated directory." >&2
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
