# Test recipes by plugin type

What to actually exercise, and what counts as evidence, for each kind of Movian
plugin. Adapted from a Mimo-format skill that was tracked in no repository;
the rest of that skill duplicated the `movian:run` loop and was not carried over.

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
