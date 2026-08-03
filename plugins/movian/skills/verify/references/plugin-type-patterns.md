# Test recipes by plugin type

What to actually exercise, and what counts as evidence, for each kind of Movian
plugin. Adapted from a Mimo-format skill that was tracked in no repository;
the rest of that skill duplicated the `movian:run` loop and was not carried over.

The recipes here say *what to exercise*. What the result then licenses you to
claim is `SKILL.md`'s evidence ladder — a recipe running clean is not by itself
a verdict.

Checked against core source; the compiled-plugin section had to be rewritten
(there is no `.so` plugin type) and the fabricated `mdev input` / `mdev resize`
subcommands removed. **The two network-backed types below fail from upstream
more often than from your change** — run the control described in `SKILL.md`
before calling a red run a plugin bug.

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
mdev stop 2>/dev/null
mdev run -p /path/to/plugin --force
mdev smoke run health --name dev         # gate: never trust a wedged instance
mdev log --errors
mdev open 'plugin:start' --timeout 15
mdev log --errors
mdev open 'plugin:search?query=test' --timeout 15
mdev log --errors
mdev shot --out /tmp/plugin-media.png
mdev stop
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
mdev stop 2>/dev/null
mdev run -p /path/to/smb2-plugin --force
mdev smoke run health --name dev         # gate: never trust a wedged instance
mdev log --errors
# Browse share
mdev open 'smb://server/share' --timeout 15
mdev log --errors
# Play a file
mdev open 'smb://server/share/video.mkv' --timeout 30
mdev log --errors
mdev props global/media/current --depth 2   # wait on the props, not the clock
mdev shot --out /tmp/smb2-playback.png
mdev stop
```

**Critical**: Protocol plugins **must** be tested with a persistent UI-backed Movian (`mdev run`, never `--no-ui`; see `CONSTRAINTS.md`). One-shot `smbclient` proves nothing about idle/keepalive paths.

**Common failures**: Signing negotiation, dialect mismatch, keepalive timeout, credential handling, large file offsets, Unicode normalization.

---

### UI/Skin Plugins

**Characteristics**: Replace or extend `.view` files, skins, fonts, GLW widgets; no network logic.

**Test patterns**:
- **View rendering**: Open each modified route → screenshot → compare to baseline
- **Focus/navigation**: drive input, then screenshot — see the input caveat below
- **Skin variants**: Test with each skin (`mdev run --skin DIR`)
- **Animation/transition**: Screenshot mid-transition (hard) or verify final state

```sh
# Skin/view test
mdev stop 2>/dev/null
mdev run -p /path/to/skin-plugin --force --skin /path/to/skin
mdev smoke run health --name dev         # gate: never trust a wedged instance
mdev open 'skin:home' --timeout 10
mdev shot --out /tmp/skin-default.png
mdev log --errors
# Drive focus (see caveat) then capture
python3 "$(mdev core)/support/devtools/mdevlib/x11_keypress.py" Down Down Activate
mdev shot --out /tmp/skin-focused.png
mdev stop
```

**Input caveat.** `mdev` has no `input` subcommand — actions go over HTTP
(`/api/input/action/<Name>`, names from `src/event.c`) or as real X11 keypresses
via `mdevlib/x11_keypress.py`. The two are not interchangeable: synthetic
`/api/input/action/...` calls do not set the keypress flag, so `isFocused()` and
the visible list cursor stay false. **For any smoke about visible focus, use X11
keypresses** (`CONSTRAINTS.md`, and the `isFocused` row in `movian:view`'s
`glw-view-language.md`).

**Use the `movian:view` skill** for isolated `.view` iteration with live reload.

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
mdev stop 2>/dev/null
mdev run -p /path/to/metadata-plugin --force
mdev smoke run health --name dev         # gate: never trust a wedged instance
mdev open 'plugin:start' --timeout 15
mdev log --errors
# Open item with known metadata
mdev open 'plugin:movie:tt1234567' --timeout 15
mdev props global/navigators/current/currentpage/model --depth 3
mdev log --errors
mdev stop
```

**Common failures**: API key rotation, schema changes, missing fallbacks, timeout handling.

---

### Compiled Plugins (`"type": "bitcode"`)

Movian accepts exactly three plugin types — `views`, `ecmascript` and `bitcode`
(`src/plugins.c:674-702`). **There is no `.so` plugin type and nothing is ever
`dlopen`ed.** A compiled plugin is LLVM bitcode executed by the bundled VMIR
interpreter, so the usual native concerns — symbol resolution, ABI drift,
`LD_LIBRARY_PATH` — do not apply. Its manifest carries `file`, and optionally
`apiversion` (default 1), `memory-size` (default 4096 KB) and `stack-size`
(default 64 KB); those become the VM's fixed allocation
(`src/plugins.c:679-698`, `src/np/np.c:400`).

**Test patterns**:
- **Core support first**: bitcode loading is compile-time gated on
  `ENABLE_VMIR`. Confirm `CONFIG_VMIR=yes` in the core's `build.debug/config.mak` before
  reading a load failure as a plugin bug — an unsupported core does not even
  reach the `bitcode` branch, so the plugin looks inert with no error naming VMIR.
- **Load test**: `mdev run` → `mdev log --errors`. A failure here is reported
  through the plugin loader's error buffer, so it names the control file or the
  missing `file` element rather than a linker message.
- **Sandbox sizing**: the VM's memory and stack are fixed at load. Exhausting
  either is a plugin-side failure and a reason to raise `memory-size` /
  `stack-size` in the manifest — not a core bug.
- **Crash reproduction**: capture a backtrace as for any core crash
  (`debug-flags.md`); the trace runs through the VMIR interpreter frames, not
  through plugin symbols.

```sh
# Bitcode plugin smoke
grep -n CONFIG_VMIR "$(mdev core)/build.debug/config.mak"   # must be yes
mdev stop 2>/dev/null
mdev run -p /path/to/bitcode-plugin --force
mdev smoke run health --name dev         # gate: never trust a wedged instance
mdev log --errors
mdev open 'plugin:start' --timeout 15
mdev log --errors
mdev stop
```

**Common failures**: core built without VMIR, missing or misnamed `file` in the
manifest, `apiversion` mismatch, memory/stack exhaustion at the configured size.
