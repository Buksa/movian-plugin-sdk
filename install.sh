#!/usr/bin/env bash
# Install the Movian SDK execution shims.
#
# The Claude Code plugin channel delivers skills (markdown) only; `mdev` and
# `movian-lsp` are executables on PATH, so they need this second channel.
#
# Usage:  ./install.sh [--fix-path|--unfix-path] [/abs/path/to/movian/core/checkout]
#
# The path argument is optional: omit it to install the shims without touching
# an existing ~/.config/movian-sdk/config.json.
#
#   --fix-path    make the shims reachable from ordinary terminals and from
#                 `ssh host 'mdev ...'`, by writing a delimited managed block
#                 into ~/.bashrc above its interactive guard. OPT-IN: without
#                 this flag nothing outside the SDK's own directories is
#                 touched, only a warning is printed (movian-plugin-sdk#39).
#   --unfix-path  remove that block again.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bindir="${MOVIAN_SDK_BINDIR:-$HOME/.local/bin}"
libdir="${MOVIAN_SDK_LIBDIR:-$HOME/.local/lib/movian-sdk}"
config="${MOVIAN_SDK_CONFIG:-$HOME/.config/movian-sdk/config.json}"

# This script had no option parsing at all until #34: `$1` was positionally the
# core path, so `./install.sh --fix-path` would have been read as one and
# rejected for not being absolute.
core=""
fixmode=""
for arg in "$@"; do
  case "$arg" in
    --fix-path)   fixmode=apply ;;
    --unfix-path) fixmode=remove ;;
    -h|--help)    sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "error: unknown option '$arg'" >&2; exit 1 ;;
    *)
      [ -z "$core" ] || { echo "error: more than one core path given" >&2; exit 1; }
      core="$arg"
      ;;
  esac
done

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
install_file "$here/lib/reachable.sh" "$libdir/reachable.sh"
install_file "$here/lib/viewdoc.py" "$libdir/viewdoc.py"
install_file "$here/lib/typefloor.py" "$libdir/typefloor.py"
install_file "$here/bin/mdev" "$bindir/mdev"
install_file "$here/bin/movian-lsp" "$bindir/movian-lsp"

if [ -n "$core" ]; then
  case "$core" in
    /*) ;;
    *) echo "error: core path must be absolute, got '$core'" >&2; exit 1 ;;
  esac
  [ -d "$core" ] || { echo "error: '$core' is not a directory" >&2; exit 1; }
  # The same diagnosis the locator gives, at the moment the path is first
  # named. Without this a new user following the documented setup with a
  # genuine Movian checkout on an older revision is told it is "not a Movian
  # checkout" and never reaches the shim that would have said otherwise.
  [ -e "$core/support/devtools/mdev" ] || {
    . "$here/lib/locate.sh"
    echo "error: $(movian_sdk_shquote "$core") has no support/devtools/mdev" >&2
    movian_sdk_explain_missing_mdev "$core"
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

# Record WHERE the shims went. Until #34 nothing on the system knew: `bindir`
# was a local here, absent from the config and from the shims' own stamps, so
# anything resolving them had to guess `~/.local/bin` — a guess that fails
# silently under MOVIAN_SDK_BINDIR, because that variable lives in this shell
# and is never exported into the agent session that needs it. The skills read
# this key instead of relying on PATH (movian-plugin-sdk#41).
#
# Merged with jq rather than rewritten, so a config carrying "core" keeps it.
# Only written when a config exists or was just created: an install with no
# core at all has nothing for mdev to do, and inventing a config here would
# turn the locator's "no Movian core configured" into "has no usable core key".
if [ -f "$config" ]; then
  tmpcfg="$(mktemp)"
  # Report the merge honestly. `jq ... && cat ...` swallows a jq failure -- it
  # is not the last command of the AND-list, so `set -e` does not fire -- and
  # the script would then print that the bindir was recorded when the config
  # was untouched, leaving the skills' fallback with no "bin" key to read.
  if jq --arg bin "$bindir" '. + {bin: $bin}' "$config" > "$tmpcfg" 2>/dev/null; then
    cat "$tmpcfg" > "$config"
    echo "  recorded bin -> $bindir in $config"
  else
    echo "  WARNING: could not record bin in $config" >&2
    echo "  it is not valid JSON, or jq is unavailable. The skills resolve mdev" >&2
    echo "  through this key, so fix the file and rerun:" >&2
    echo "    {\"core\": \"/abs/path/to/movian\", \"bin\": \"$bindir\"}" >&2
  fi
  rm -f "$tmpcfg"
fi

# The reachability question, asked of the shells that will RUN mdev rather than
# of this one. The check it replaces tested `:$PATH:` of the installer's own
# shell, which is wrong in both directions at once (movian-plugin-sdk#34): it
# warned from a shell that happened to carry the directory, and stayed silent
# from a login shell while every ordinary terminal failed.
. "$here/lib/reachable.sh"

if [ -n "$fixmode" ]; then
  echo
  echo "PATH:"
  movian_sdk_fix_path "$HOME/.bashrc" "$bindir" "$fixmode"
fi

echo
movian_sdk_reachability_report "$bindir"
if [ "$MOVIAN_SDK_REACH_WORST" != REACHABLE ]; then
  echo
  movian_sdk_explain_unreachable "$bindir" "$here" "$MOVIAN_SDK_REACH_WORST"
fi
# Deliberately not a gate: the files ARE installed, and reachability is a
# property of the user's shell configuration. Same ruling as the locator's —
# a command, not a gate (movian-plugin-sdk#3).

echo
echo "Verify from any plugin repo (not from the core):"
echo "    mdev doctor"
