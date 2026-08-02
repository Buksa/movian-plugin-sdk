---
name: run
description: Launch, stop, drive and observe a Movian instance from a plugin repo using the mdev harness — run with a dev plugin, open a route, screenshot, read logs and props, hot-reload views and plugin JS. Use when asked to run or restart Movian, load a plugin into it, open a route, take a screenshot, tail the log, inspect props, or reload a changed file. Judgment about whether a result proves anything lives in the verify skill.
---

# Running Movian from a plugin repo

Mechanics only. **What counts as proof is a separate question** — see the
`movian:verify` skill. This skill gets Movian running and gets data out of it.

`mdev` resolves the core checkout itself, so every command here works from any
cwd — your plugin repo, a subdirectory, anywhere. If it cannot find a core, see
`movian:locate`.

## The loop

```
mdev run [start_url] [--name NAME] [-p PLUGIN_DIR ...] [--skin DIR] \
         [--dev-flags K=1,K2=1] [--libav-log] [--force]
mdev open <url> [--name NAME] [--timeout SECONDS]     # default timeout 20s
mdev shot [--name NAME] [--out PATH] [--if-changed]
mdev stop [--name NAME]
```

From a plugin repo, load the plugin you are working on with `-p .`:

```
mdev run -p . page:home
```

Relative paths in `-p` and `--skin` resolve against **your** cwd, not the core —
so `-p .` means this plugin. (`mdev preview` and `mdev watch --dir` are the
exception: they still absolutise against the core checkout. Pass absolute paths
to those two.)

All state for one named instance lives under `/tmp/mdev/<name>/` — `state.json`,
`movian.log`, `persistent/`, `cache/`, `shots/`. The default instance name is
`dev`; `mdev preview` uses `preview`. Multiple named instances coexist, so a
long-running instance and a throwaway one do not collide.

`--dev-flags k=1` seeds `<persistent>/settings/dev` as JSON before launch — the
profile-scoped way to turn on subsystem debug output (`smbdebug=1` and friends).
See `references/debug-flags.md` for the full flag surface.

## Observing

```
mdev log [--tail N] [--errors] [--name NAME]
mdev props <path> [--name NAME]
mdev shot --if-changed
```

- `mdev log --errors` applies the standard error-signal filter rather than
  dumping everything; use it before reading raw log.
- `mdev props` takes slash-separated paths starting at `global`. Unnamed children
  display as `*N`, which is an HTTP display alias, **not** a real path segment.
- `mdev shot` prints `sha256=<hex>` and stores it as `last_shot_hash`. Exit code
  3 from `--if-changed` means the bytes were identical to the previous capture.

For structured inspection beyond these — JSON snapshots, live prop watching,
STPP probing, synthetic keypress and pointer injection — reach into the core's
`mdevlib` modules:

```
(cd "$(mdev core)/support/devtools" && python3 -m mdevlib.movian_agent snapshot ...)
```

`mdev core` prints the resolved core root, so this works from anywhere. Exact
invocations are in `references/httpcontrol-stpp.md` and
`references/prop-debugging.md` of the `movian:verify` skill.

## Reloading without restarting

```
mdev reload [--js] [--name NAME]
mdev watch [--js] [--dir DIR] [--name NAME]
```

`.view` files and dev-plugin JS reload by different mechanisms; `--js` selects
the plugin-JS path. **A clean exit code is not proof the reload worked** — the
reload check only greps for GLW parser/preprocessor errors, so a `.view` lexer
error or a failed file open passes silently. Always read `mdev log --tail`
afterwards. The `movian:view` skill covers the edit/reload loop in full.

## Coexistence

Movian instances started outside `mdev` are not owned by it. Before assuming
nothing is running, match on the **basename**, not a bare substring — a
substring match will happily find an unrelated process and mislead you.
`mdev run --force` takes over a stale instance of the same name.

## When there is no built core

`mdev` fails with a diagnosis naming the configured path and the fix. Building
is the core repo's business, not a plugin repo's; see `movian:locate`.
