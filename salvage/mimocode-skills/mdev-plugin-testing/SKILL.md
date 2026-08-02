---
name: mdev-plugin-testing
description: Use when testing a Movian plugin with the mdev dev harness. Covers the full stop→run→open→screenshot→check-errors loop. Trigger on "test plugin", "mdev run", "mdev preview", "reload plugin", or when verifying plugin changes in a live Movian instance.
---

# mdev Plugin Testing

Standardized loop for testing Movian plugins via the `mdev` devtools CLI.

## Prerequisites

- Build Movian first: `./support/configure-linux-debug.sh && make BUILD=debug -j$(nproc)`
- Working directory must be the Movian repo root
- Plugin path must be absolute (e.g., `~/movian-plugin-anilibria`)

## Testing Loop

### 1. Stop any running instance

```sh
./support/devtools/mdev stop 2>/dev/null
```

Always stop first. `mdev run --force` alone does not kill a previous instance reliably.

### 2. Launch with plugin

```sh
./support/devtools/mdev run -p /path/to/plugin --force
```

Wait 3 seconds for Movian to initialize before issuing commands.

### 3. Check startup errors

```sh
sleep 3 && ./support/devtools/mdev log --errors
```

If errors appear, capture the full log before proceeding:
```sh
./support/devtools/mdev log --tail 50
```

### 3.5 Dismiss the first-launch popup (fresh profiles only)

Required whenever the profile is fresh — a new `--name`, or anything that wiped
`/tmp/mdev/<name>/persistent`. Movian shows a first-launch popup (plugin TOS) and
until it is dismissed **navigation silently does not work**: `/api/open` returns
success, `currentpage/url` even shows the requested route, but the navigator
stays at `page:home` with `(void)` model props and no usable nodes.

Check first — a non-empty `global/popups` means one is pending:

```sh
./support/devtools/mdev props global/popups --depth 2
```

Two ways to clear it:

```sh
# A. Targeted (preferred; independent of focus)
PORT=$(python3 -c "import json;print(json.load(open('/tmp/mdev/<name>/state.json'))['port'])")
curl -s -X POST -d 'action=Ok' "http://127.0.0.1:$PORT/api/prop/global/popups/*0/eventSink"

# B. By selection (what the smoke runner does — global input action)
curl -s -X POST "http://127.0.0.1:$PORT/api/input/action/Ok"
```

Method B is the same mechanism `support/devtools/smokes/keyboard-mode.json` uses
via its `{"do": "action", "name": "down"}` steps; it relies on the popup holding
focus, which it does on first launch.

Three things that waste time if missed:

- The action must be a **POST with a form body** (`-d 'action=Ok'`). Passing it
  as a query parameter makes this HTTP server reset the connection.
- `*0` is an **HTTP display alias** for an unnamed child, not a real path
  segment. It works in the eventSink URL but shows `<not found>` in `mdev props`,
  and it is never valid in an STPP path (`popups.*0.username` is wrong — STPP
  must subscribe to `popups`, recover the child propref, and set fields relative
  to it).
- Read `PORT` from `state.json`; it is dynamically assigned, never hardcoded
  `42000`.

Skip this step only when the popup itself is what you are testing — but then do
not expect route navigation to work until it is closed.

### 4. Open test pages

```sh
./support/devtools/mdev open '<route>' --timeout 15
```

`mdev open` reporting success is **not** proof the route rendered. Confirm the
page's own props — a real `metadata.title` and `model.loading` of `0` or void —
before treating the step as passed.

Examples:
- `anilibria:start` — home/catalog page
- `anilibria:schedule` — schedule page
- `anilibria:release:10255` — specific release page
- `anilibria:search?query=naruto` — search results

After each page open, check for errors:
```sh
./support/devtools/mdev log --errors
```

### 5. Take screenshots

```sh
./support/devtools/mdev shot --out /tmp/movian-test-<name>.png
```

Always follow a shot with an error check — screenshots can trigger rendering paths that surface bugs.

### 6. Inspect props (optional)

```sh
./support/devtools/mdev props global/navigators/current/currentpage/nodes --depth 1
```

Useful for verifying catalog items, URLs, metadata binding.

### 7. Stop when done

```sh
./support/devtools/mdev stop
```

## Common Patterns

### Quick smoke test (home page only)

```sh
./support/devtools/mdev stop 2>/dev/null
./support/devtools/mdev run -p ~/movian-plugin-anilibria --force
sleep 3
./support/devtools/mdev log --errors
./support/devtools/mdev open 'anilibria:start' --timeout 15
./support/devtools/mdev log --errors
./support/devtools/mdev shot --out /tmp/movian-smoke.png
./support/devtools/mdev stop
```

### Multi-page test (home + schedule + release)

```sh
./support/devtools/mdev stop 2>/dev/null
./support/devtools/mdev run -p ~/movian-plugin-anilibria --force
sleep 3
# Home
./support/devtools/mdev open 'anilibria:start' --timeout 15
./support/devtools/mdev log --errors
# Schedule
./support/devtools/mdev open 'anilibria:schedule' --timeout 15
./support/devtools/mdev log --errors
# Release
./support/devtools/mdev open 'anilibria:release:10255' --timeout 15
./support/devtools/mdev log --errors
./support/devtools/mdev shot --out /tmp/movian-release.png
./support/devtools/mdev stop
```

### Reload after code change (no full restart)

```sh
./support/devtools/mdev reload --name preview --json
```

This is faster than stop+run but only works for hot-reloadable changes (skin/view edits, not C recompilation).

## Gotchas

- **Always `sleep 3` after `mdev run`** — Movian needs time to initialize the UI event loop before it accepts `open`/`shot` commands.
- **`mdev open` with `--timeout 15`** — Some pages take time to fetch API data. The default timeout is too short for network-dependent pages.
- **`--force` is an owned restart, not a cleanup bypass** — it terminates only the PID confirmed for this instance, refuses same-directory collisions, and exits 2 instead of launching when the owned PID survives SIGKILL.
- **Plugin path must be absolute** — `mdev` does not resolve relative paths correctly.
- **Check errors after EVERY page load** — Some bugs only appear on specific routes (e.g., schedule rendering, release metadata binding).
- **Headless launch self-terminates** — Movian without a persistent UI event loop exits ~3s after startup. Never use `--no-ui` or headless mode for plugin testing.
- **Orca automation launches require `--dangerously-skip-permissions`** — When launching `mimo` from an Orca worktree or pipeline automation, the flag is mandatory. Without it, the process blocks on permission prompts and the automation stalls. See `verifier-checks` Rule 5.

## Wedge cleanup and stop outcomes

When an mdev smoke or health check classifies an instance as wedged:

1. **Diagnostics BEFORE cleanup**: Capture the failure bundle (props.json, steps.json, log-tail.txt) while the owned instance is still alive. A stopped/dead process cannot serve its current-page prop tree — the bundle must contain live diagnostic data, not post-mortem dead-PID messages.
2. **Owned-PID-only kill**: `kill_owned_pid()` only signals processes whose `/proc/<pid>/cmdline` matches the mdev instance. It never cross-signals a different PID.
3. **Bounded wait + SIGKILL escalation**: The wedge path waits for the process to exit, then escalates to SIGKILL on timeout. The outcome is recorded as `stopped-clean` or `killed-after-timeout` in `steps.json`.
4. **Forced restart refusal**: `mdev run --force` raises exit 2 and refuses to launch when the owned pid remains alive. This prevents launching against a persistent directory that still has a live instance.

The smoke runner's "stop+relaunch" wedge path now performs the owned stop and records its outcome. Relaunch is safe only when the outcome is not `still-alive`.

## Screenshot hash and state contracts

The `mdev shot` command now computes a raw-byte SHA-256 before any file creation:

- **Compare-before-write**: If `--if-changed` is supplied and the newly computed hash matches the prior hash, `take_shot()` returns immediately — no file is written, no path is created, no state is modified.
- **Unchanged output**: Exit 3 with a one-line result (`unchanged <path> sha256=<hex>` human, or `{"path":..., "unchanged": true, "sha256":...}` JSON). The retained path is always absolute and survives cwd changes.
- **Changed output**: Exit 0 with a new path and hash. State records `last_shot_path` (absolute, resolved) and `last_shot_hash`.
- **Cache key**: The vision-cache is keyed on `(sha256, exact question)` — equal bytes with different questions still require a vision call. Exit 3 alone is NOT a verdict-cache hit.
- **State ordering**: `save_state()` (launch) and `record_shot_hash()` share one exclusive `fcntl.flock(LOCK_EX)`. Writes use atomic `.tmp` → `.replace()`. Both lock orderings (record-then-save, save-then-record) are safe — the lock prevents torn reads.
- **Caller-relative paths**: `--out relative.png` resolves to absolute at capture time. The absolute path is stored in `last_shot_path` and returned on exit 3 from any cwd.

## Portable file copy

When copying binaries, build artifacts, or test fixtures during verification:

```sh
cp --reflink=always "$src" "$dst" 2>/dev/null || cp "$src" "$dst"
```

`cp --reflink=always` requires CoW filesystem support (btrfs, XFS). On ext4 (Ubuntu default, CI runners, Steam Deck), it fails with "Operation not supported". The normal `cp` fallback is always safe. See `verifier-checks` Rule 3.

## Plugin-Type Testing Patterns

### Media Source Plugins (e.g., anilibria, streaming services)

**Characteristics**: Fetch catalog/metadata from HTTP APIs, render item lists, play media via Movian's player.

**Test patterns**:
- **Catalog load**: Open start page → verify `model.items` populated, `metadata.title` present
- **Pagination/infinite scroll**: Scroll to bottom → `mdev props` shows new items appended
- **Search**: Open `plugin:search?query=X` → verify results, check error log for API failures
- **Playback**: Open item → `mdev open 'plugin:play:<id>'` → check `log --errors` for player init
- **Artwork loading**: Screenshot → verify images render (no broken placeholders)

```sh
# Media plugin smoke
./support/devtools/mdev stop 2>/dev/null
./support/devtools/mdev run -p /path/to/plugin --force
sleep 3
./support/devtools/mdev log --errors
./support/devtools/mdev open 'plugin:start' --timeout 15
./support/devtools/mdev log --errors
./support/devtools/mdev open 'plugin:search?query=test' --timeout 15
./support/devtools/mdev log --errors
./support/devtools/mdev shot --out /tmp/plugin-media.png
./support/devtools/mdev stop
```

**Common failures**: API schema changes, auth token expiry, geo-blocking, rate limits, malformed metadata.

---

### Protocol Plugins (SMB2, NFS, WebDAV, etc.)

**Characteristics**: Implement filesystem/network protocols, expose as virtual filesystem, handle auth/signing/keepalive.

**Test patterns**:
- **Mount/share browse**: Open `protocol://server/share` → verify directory listing
- **File read**: Open a media file → verify playback starts, check seek/resume
- **Auth/signing**: Test with signed/unsigned server, verify negotiation (SMB2 signing)
- **Keepalive/idle**: Hold connection open >30s → issue second operation → verify no reconnect
- **Large file/transfer**: Copy large file → verify progress, no truncation
- **Unicode/international**: Filenames with UTF-8, CJK, emoji → verify listing/read

```sh
# SMB2 protocol test (requires running Samba/server)
./support/devtools/mdev stop 2>/dev/null
./support/devtools/mdev run -p /path/to/smb2-plugin --force
sleep 3
./support/devtools/mdev log --errors
# Browse share
./support/devtools/mdev open 'smb://server/share' --timeout 15
./support/devtools/mdev log --errors
# Play a file
./support/devtools/mdev open 'smb://server/share/video.mkv' --timeout 30
./support/devtools/mdev log --errors
sleep 5  # Let playback settle
./support/devtools/mdev shot --out /tmp/smb2-playback.png
./support/devtools/mdev stop
```

**Critical**: Protocol plugins **must** be tested with a persistent UI-backed Movian (see "Headless launch self-terminates" gotcha). One-shot `smbclient` proves nothing about idle/keepalive paths.

**Common failures**: Signing negotiation, dialect mismatch, keepalive timeout, credential handling, large file offsets, Unicode normalization.

---

### UI/Skin Plugins

**Characteristics**: Replace or extend `.view` files, skins, fonts, GLW widgets; no network logic.

**Test patterns**:
- **View rendering**: Open each modified route → screenshot → compare to baseline
- **Focus/navigation**: `mdev input action Down/Up/Left/Right/Ok` → verify focus moves correctly
- **Skin variants**: Test with each skin (`--skin default`, `--skin dark`, etc.)
- **Responsive layout**: Resize via `mdev resize WIDTH HEIGHT` → verify no overlap/clipping
- **Animation/transition**: Screenshot mid-transition (hard) or verify final state

```sh
# Skin/view test
./support/devtools/mdev stop 2>/dev/null
./support/devtools/mdev run -p /path/to/skin-plugin --force --skin default
sleep 3
./support/devtools/mdev open 'skin:home' --timeout 10
./support/devtools/mdev shot --out /tmp/skin-default.png
./support/devtools/mdev log --errors
# Test focus
./support/devtools/mdev input action Down
./support/devtools/mdev input action Down
./support/devtools/mdev input action Ok
./support/devtools/mdev shot --out /tmp/skin-focused.png
./support/devtools/mdev stop
```

**Use `movian-view-design` skill** for isolated `.view` iteration with live reload.

**Common failures**: Missing view dependencies, font loading, skin variable references, focus traps, layout overflow.

---

### Service Integration Plugins (metadata, subtitles, etc.)

**Characteristics**: Call external APIs (TMDB, OpenSubtitles, etc.), augment media with metadata/subtitles.

**Test patterns**:
- **Metadata fetch**: Play known item → verify `metadata.*` props populated (title, year, plot, poster)
- **Subtitle search/download**: Trigger subtitle search → verify list → select → verify load
- **Rate limit/auth**: Test with/without API key, verify graceful degradation
- **Cache behavior**: Repeat request → verify cached (no network log entries)

```sh
# Metadata plugin test
./support/devtools/mdev stop 2>/dev/null
./support/devtools/mdev run -p /path/to/metadata-plugin --force
sleep 3
./support/devtools/mdev open 'plugin:start' --timeout 15
./support/devtools/mdev log --errors
# Open item with known metadata
./support/devtools/mdev open 'plugin:movie:tt1234567' --timeout 15
./support/devtools/mdev props global/navigators/current/currentpage/model --depth 3
./support/devtools/mdev log --errors
./support/devtools/mdev stop
```

**Common failures**: API key rotation, schema changes, missing fallbacks, timeout handling.

---

### Native/Compiled Plugins (C/ECMAScript with build step)

**Characteristics**: Require `make`/`ninja` build, `.so` modules, C API bindings; changes need rebuild.

**Test patterns**:
- **Build verification**: `make BUILD=debug -j$(nproc)` in plugin dir → verify `.so` produced
- **Load test**: `mdev run` → check `log --errors` for `dlopen` failures, symbol mismatches
- **ABI compatibility**: Test against Movian built with same `configure` flags
- **Memory/leaks**: Long-running playback → `mdev log --tail 100` → check for leaks
- **Crash reproduction**: Trigger known crash path → capture backtrace (coredump or log)

```sh
# Native plugin test
cd /path/to/native-plugin
make BUILD=debug clean all
./support/devtools/mdev stop 2>/dev/null
./support/devtools/mdev run -p /path/to/native-plugin --force
sleep 3
./support/devtools/mdev log --errors | grep -iE "dlopen|symbol|segfault|abort"
./support/devtools/mdev open 'native:test' --timeout 15
./support/devtools/mdev log --errors
./support/devtools/mdev stop
```

**Critical**: Always rebuild after Movian core changes. Native plugins break silently on ABI mismatch.

**Common failures**: Missing symbols, version mismatch, memory corruption, threading issues, build flag drift.
