---
name: locate
description: Find the Movian core checkout and its built binary from inside a plugin repo, and diagnose the locator when mdev or movian-lsp fail. Use when asked where the Movian core is, when `mdev` or `movian-lsp` report an unresolved core, when setting up a machine for Movian plugin work, or when a plugin repo needs the core's devtools (mdev, movian-lsp, the .d.ts generator).
---

# Locating the Movian core from a plugin repo

A Movian plugin repo contains no build system and no devtools. Everything that
builds, launches, or inspects Movian lives in a checkout of the **core** repo
(`buksa/movian`), which is a separate repository. This skill is how you reach it.

**Sentinel for delivery checks: `MOVIAN_SDK_LOCATE_OK`.** If you can read this
line, the `movian` plugin is installed and its skills are reaching this session.

## The contract

One designated core per machine, resolved in this order:

1. `MOVIAN_CORE` — environment variable, overrides everything. Scoped to one
   session, so a single agent can target a different core without disturbing
   any other session running on the machine.
2. `~/.config/movian-sdk/config.json` — `{"core": "/abs/path/to/checkout"}`.
3. **Hard fail.** There is deliberately no search fallback: more than one built
   checkout usually exists, and worktree tooling keeps creating more, so a
   heuristic would silently guess wrong.

## Using it

`mdev` and `movian-lsp` on `PATH` are shims that apply the contract for you.
Run them from anywhere — a plugin repo, a subdirectory, any cwd:

```
mdev doctor          # what core resolved, how, and whether it is usable
mdev --help          # full harness: run / stop / open / shot / smoke / props / log
movian-lsp --stdio   # LSP over plugin .js and .view
```

`mdev doctor` is the first thing to run when anything is wrong. It reports the
resolved core and how it resolved, the binary's build time and version, the
checkout's HEAD and how far it is behind `origin/movian6`, whether any C source
is newer than the binary, and whether the devtools set is complete — then
delegates to the core's own `mdev lsp doctor`.

To point one session at a different core:

```
MOVIAN_CORE=/path/to/other/checkout mdev doctor
```

## Validation is presence, not freshness

The shim checks only that the core exists, has `support/devtools/mdev`, and has
an executable `build.debug/movian`. It never gates on the binary being current
and never builds anything.

This is deliberate. Plugin work edits JavaScript, which never invalidates the
core's C build, so a freshness gate would fire on nearly every run and train
agents to ignore it. `mdev doctor` reports freshness on demand instead.

## When it fails

Every failure names the offending path and the fix. The common ones:

- **"no Movian core configured"** — neither `MOVIAN_CORE` nor the config file is
  set. Create `~/.config/movian-sdk/config.json` with the core path.
- **"has no support/devtools/mdev"** — four different causes, and the second
  line of the message says which. Read it rather than assuming the path is
  wrong:
  - *"not of Movian"* or no second line — the path really is not a Movian
    checkout. The markers are `support/configure.inc` and `src/prop/prop.h`
    in HEAD, together: a bare C project with `src/main.c` is not enough.
    Point somewhere else.
  - *"it IS a Movian checkout — on `<branch>` @ `<sha>`, a revision without
    it"* — the path is right and the **revision** is old. Update that checkout,
    or point at one whose revision carries `support/devtools/mdev`.
  - *"this revision DOES carry it — the working-tree copy is missing"* — a
    deleted file, or a sparse checkout that excludes `support/`. Restore it
    with `git checkout HEAD --ignore-skip-worktree-bits -- support/devtools/mdev`.
    Both parts are load-bearing: without `HEAD` the pathspec is read from the
    index, where a `git rm --cached` has already removed it, and without the
    flag a sparse-checkout exclusion refuses the pathspec. Updating the
    checkout does nothing in any of these cases. If sparse-checkout is the
    cause, widen the patterns too or the next checkout drops it again.
  - *"that path is inside the Movian checkout at `<root>`"* — you pointed into
    the tree instead of at it. Point at `<root>`.
- **"has no executable build.debug/movian"** — the core is not built. Build it
  **from the checkout that owns its `build.debug`**:

  ```
  cd <core> && ./support/configure-linux-debug.sh && make BUILD=debug -j$(nproc)
  ```

  Never run `configure` from a worktree whose `build.debug` is shared or
  symlinked — it rewrites the shared `config.mak` with that worktree's `TOPDIR`
  and breaks every checkout that shares it, and the breakage surfaces elsewhere
  long after the command that caused it.

- **`mdev lsp doctor` reports `movian-analyze` missing** — that target is not
  part of the default build. Add it: `make BUILD=debug -j$(nproc) movian-analyze`.

## Editor and agent intelligence

`movian-lsp` serves both `.view` and plugin `.js`. A plugin repo enables it with
one file at its root, `.lsp.json`:

```json
{
  "servers": {
    "movian-lsp": {
      "command": "movian-lsp",
      "args": ["--stdio"],
      "fileTypes": [".view", ".js"],
      "rootMarkers": ["plugin.json"]
    }
  }
}
```

`command` is the **shim on `PATH`**, not a path into the core — the shim resolves
the core itself, which is what makes one config work in every repo. `plugin.json`
as the root marker scopes it to plugin repos rather than any git checkout.

Confirm it took: an OMP session in the repo lists `movian-lsp .view .js` under
LSP Servers instead of `No LSP servers`.

## Installing the shims

The shims are executables on `PATH`, so the Claude Code plugin cannot deliver
them — a plugin ships skills, not binaries. Install them from the SDK repo:

```
git clone https://github.com/Buksa/movian-plugin-sdk
cd movian-plugin-sdk && ./install.sh /abs/path/to/movian/checkout
```

This writes `~/.local/bin/mdev`, `~/.local/bin/movian-lsp`,
`~/.local/lib/movian-sdk/locate.sh`, and the config file.
