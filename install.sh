#!/usr/bin/env bash
# Install the Movian SDK execution shims.
#
# The Claude Code plugin channel delivers skills (markdown) only; `mdev` and
# `movian-lsp` are executables on PATH, so they need this second channel.
#
# Usage:  ./install.sh [/abs/path/to/movian/core/checkout]
#
# The path argument is optional: omit it to install the shims without touching
# an existing ~/.config/movian-sdk/config.json.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bindir="${MOVIAN_SDK_BINDIR:-$HOME/.local/bin}"
libdir="${MOVIAN_SDK_LIBDIR:-$HOME/.local/lib/movian-sdk}"
config="${MOVIAN_SDK_CONFIG:-$HOME/.config/movian-sdk/config.json}"
core="${1:-}"

mkdir -p "$bindir" "$libdir" "$(dirname "$config")"

# Never clobber silently: an existing file that differs is backed up first.
# Shims carry a default MOVIAN_SDK_LIB; rewrite it so a non-default --libdir
# install produces a shim that actually finds its own resolver. MOVIAN_SDK_ROOT
# is stamped the same way: `mdev viewdoc` validates docs that live in this
# checkout, so the installed shim has to remember where the checkout is. It is
# recorded, never searched for — same contract as the core locator.
install_file() {
  local src="$1" dst="$2" tmp
  tmp="$(mktemp)"
  sed -e "s|^MOVIAN_SDK_LIB=.*|MOVIAN_SDK_LIB=\"\${MOVIAN_SDK_LIB:-$libdir}\"|" \
      -e "s|^MOVIAN_SDK_ROOT=.*|MOVIAN_SDK_ROOT=\"\${MOVIAN_SDK_ROOT:-$here}\"|" \
      "$src" > "$tmp"
  if [ -e "$dst" ] && ! cmp -s "$tmp" "$dst"; then
    local bak="$dst.bak-$(date +%Y%m%d%H%M%S)"
    cp -p "$dst" "$bak"
    echo "  backed up existing $dst -> $bak"
  fi
  install -m 755 "$tmp" "$dst"
  rm -f "$tmp"
  echo "  installed $dst"
}

echo "Installing Movian SDK shims:"
install_file "$here/lib/locate.sh" "$libdir/locate.sh"
install_file "$here/lib/viewdoc.py" "$libdir/viewdoc.py"
install_file "$here/bin/mdev" "$bindir/mdev"
install_file "$here/bin/movian-lsp" "$bindir/movian-lsp"

if [ -n "$core" ]; then
  case "$core" in
    /*) ;;
    *) echo "error: core path must be absolute, got '$core'" >&2; exit 1 ;;
  esac
  [ -d "$core" ] || { echo "error: '$core' is not a directory" >&2; exit 1; }
  [ -e "$core/support/devtools/mdev" ] || {
    echo "error: '$core' has no support/devtools/mdev — not a Movian checkout" >&2
    exit 1
  }
  printf '{\n  "core": "%s"\n}\n' "$core" > "$config"
  echo "  wrote $config -> $core"
elif [ -f "$config" ]; then
  echo "  kept existing $config"
else
  echo
  echo "No core configured. Either re-run with the checkout path:"
  echo "    ./install.sh /abs/path/to/movian"
  echo "or write $config yourself:"
  echo "    {\"core\": \"/abs/path/to/movian\"}"
fi

case ":$PATH:" in
  *":$bindir:"*) ;;
  *) echo; echo "warning: $bindir is not on PATH — add it to use mdev directly." ;;
esac

echo
echo "Verify from any plugin repo (not from the core):"
echo "    mdev doctor"
