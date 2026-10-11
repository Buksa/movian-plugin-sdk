# What mdev needs from a core, and what movian-go provides

> **Point-in-time survey. Measure again before acting on it.**
> Investigated on the date stated below against the checkouts as they stood then. Both
> cores move, and their line numbers go stale first. **No movian-go instance and no C
> instance was launched, and nothing was built.** Every claim about how movian-go behaves
> at *runtime* comes from reading its code, and is marked **[INFER]** wherever it
> predicts an outcome. No corrections have been found against this file.

Research for making `mdev` work against movian-go, part of the wayfinder map
[issue #1 "Wayfinder: portable Movian plugin-dev layer"](https://github.com/Buksa/movian-plugin-sdk/issues/1).
Investigated 2026-10-10.

**Sources.** Citation prefixes: `core:` is the C core, `go:` is movian-go, `sdk:` is this repo.

- **[READ]** — read-only reading, cited `prefix:path:line`.
  - `core:` `/home/uzver/movian-public-clean`, branch `movian6` @ `593627edd`. This is the
    core that `~/.config/movian-sdk/config.json` designates. `/home/uzver/movian` (older)
    was not used.
  - `go:` `/home/uzver/movian-go` @ `10775f3` (module `github.com/czz/movian-go`, Go 1.26).
    **The working tree is dirty.** `ffmpeg/lib/pkgconfig/*.pc`, two `glwskins/flat/*youtube*.view` files and
    `internal/i18n/i18n.go` are modified, and `AGENTS.md` and `docs/agents/` are untracked.
    No cited Go file is among the modified ones.
  - `sdk:` `/home/uzver/movian-plugin-sdk` @ `c2e200e`.
- **[MEASURED]** — harmless read-only commands, all run 2026-10-10:
  - the shims run with `MOVIAN_CORE=/home/uzver/movian-go`;
  - `./movian-go --help`, using the binary already in the movian-go root. It was built
    2026-10-08 18:50, after the HEAD commit, and was not rebuilt. Its provenance against
    the dirty tree is unknown;
  - `ldd`, `git ls-files`, `diff -rq` of `res/ecmascript`;
  - two throwaway regex scripts in the session scratchpad, not committed. They compare the
    native-module function tables (`duk_function_list_entry` against
    `gaftape.FunctionListEntry`) and the GLW name tables against
    `core:generated/movian-metadata.json`.
- **[INFER]** — the conclusion follows from the cited code but was not observed. Each one
  names what would settle it.

---

## 0. Summary

**Today the SDK cannot reach movian-go at all.** The locator rejects it at its first
check, and its diagnosis calls movian-go "not of Movian" [MEASURED §1]. Behind the locator
there is nothing to hand off to. The whole execution layer (`support/devtools/`: Python
`mdevlib`, smokes, the viewpreview plugin, metadata generator, LSP, analyzer and gdb
collector) lives *inside the C core*, and movian-go has no counterpart to any of it.

Most of the HTTP surface matches mdev's needs in shape: open, prop text, raw screenshot,
STPP JSON, ecmascript stats and the CLI flags. **What is missing is mdev's proof signals.**
mdev proves an operation from log lines and side effects, and these are where movian-go
differs:

- the port line;
- the navigator `Opening` trace;
- dev-plugin reload and its log lines;
- HTTP actions reaching the UI with the keypress flag;
- GLW error tracing for every view load failure;
- process identity by `comm`.

Several of these were added to the C fork *for tooling*, for example `core:src/api/httpcontrol.c:234-240`
and `core:src/ui/glw/glw_view.c:280-284`.

### Summary table

Status values: **same**, **different**, **absent** or **unknown**. "Same" means the same in
code, not verified at runtime unless it is marked [MEASURED].

| # | area | what mdev needs | movian-go | evidence |
|---|---|---|---|---|
| L1 | locator | `support/devtools/mdev` in core root | **absent** | sdk:lib/locate.sh:193; no `support/` in go: [MEASURED] |
| L2 | locator | C build markers at HEAD (`support/configure.inc` + `src/prop/prop.h`) to call it "Movian" | **absent**: diagnosed "not of Movian" | sdk:lib/locate.sh:114-119 [MEASURED §1] |
| L3 | locator | executable `build.debug/movian` | **different**: `./movian-go` | sdk:lib/locate.sh:198; go:Makefile:162 |
| L4 | `mdev types`, doctor | `generated/movian-api.d.ts` | **absent** | sdk:bin/mdev:44,148 |
| L5 | `mdev viewdoc` | `generated/movian-metadata.json` | **absent** | sdk:bin/mdev:100 |
| L6 | `mdev doctor` | `src/**.c` mtimes, `origin/movian6`, nine devtools dirs, core `mdev lsp doctor` | **absent** / meaningless | sdk:bin/mdev:117-140,203 |
| L7 | install.sh | core path carries `support/devtools/mdev` | **absent** | sdk:install.sh:100-104 |
| B1 | build | `configure-linux-debug.sh` + `make BUILD=debug` | **different**: `make ffmpeg` (one-off) + `make build` | sdk:lib/locate.sh:200; go:Makefile:159-162; go:BUILDING.md:62-73 |
| B2 | build | native deps a C build already has | **different**: vendored static FFmpeg 9.0.1 (gated), GLFW ≥ 3.4, optional CEF | go:Makefile:37,129-147; go:BUILDING.md:44-64 |
| B3 | build | `movian-analyze` target (for LSP) | **absent**: one `cmd/` only | core:Makefile:1001-1049; go:cmd/ [MEASURED] |
| R1 | launch | flags `-d --disable-upgrades --persistent --cache -p --skin --libav-log --bypass-ecmascript-acl <url>` | **same** (all parsed) | core:support/devtools/mdevlib/harness.py:348-368; go:cmd/movian-go/parseopts.go:103-245,305-308 |
| R2 | launch | cwd = core root resolves `dataroot://` | **same** | core:…/harness.py:383; go:internal/app/dataroot.go:24-38 |
| R3 | readiness | log line `http-server: Listening on port N` | **absent** | core:…/harness.py:38,411; go:internal/networking/http/http_server.go:395-409 |
| R4 | launch | port 42000 with ephemeral fallback, so instances coexist | **different**: fixed 42000, no fallback | core:src/networking/http_server.c:1166-1167; go:cmd/movian-go/wire_network.go:451,461-463 |
| R5 | lifecycle | `/proc/<pid>/comm == "movian"` or argv basename `movian` | **different**: `movian-go` [INFER] | core:…/harness.py:200-231,287-292 |
| R6 | stop | SIGTERM, then SIGKILL, of the owned pid | **same outcome** [INFER]: no SIGTERM handler on desktop | go:internal/arch/arch.go:644-652 |
| R7 | lifecycle | `MOVIAN_MDEV_ALLOW_GDB=1` → `PR_SET_PTRACER_ANY` | **absent** | core:src/arch/linux/linux_misc.c:156-165 |
| R8 | launch | `--dev-flags` seeds `<persistent>/settings/dev` | **same** store key | core:…/cli.py:73-79; go:internal/settings/dev/devsettings.go:48-72 |
| R9 | log | stdout+stderr capture; prefix `%-15s [%-5s]:` | **same** prefix (+ Go `log` date stamp) | go:internal/trace/trace.go:182,212-214 |
| H1 | open | `GET /api/open?url=` queues the open and returns 302 | **same** | core:src/api/httpcontrol.c:50-65; go:internal/api/httpcontrol/httpcontrol.go:59-85 |
| H2 | open/preview/health | trace `navigator … Opening <url>` per open | **absent** | core:src/navigator.c:763; go:internal/navigator/navigator_open.go:315-346 |
| H3 | open | page props under `global/navigators/current/currentpage` | **same** names | core:…/harness.py:86-95; go:internal/navigator/navigator_open.go:168-174,255 |
| H4 | props | `GET /api/prop/<path>` text body, `*N` indexing | **same** | core:src/prop/prop_http.c:147-238; go:internal/prop/http/prop_http.go:125-175 |
| H5 | props, smokes | missing path → 404, no side effect | **different**: GET creates the prop and returns 200 `(void)` | core:src/prop/prop_core.c:5049-5091; go:internal/prop/http/prop_http.go:36 → go:internal/prop/prop_registry.go:233-236 |
| H6 | prop-debug | `POST /api/prop` `debug=on\|off`, `action=` | **same** | core:src/prop/prop_http.c:124-145; go:internal/prop/http/prop_http.go:105-123 |
| H7 | reload, action, smoke | `/api/input/action/<A>` goes to the UI (`event_to_ui`) | **different**: `event_dispatch` path; [INFER] ReloadUI and arrows never reach GLW | core:src/api/httpcontrol.c:259; go:internal/api/httpcontrol/httpcontrol.go:103-105 |
| H8 | keyboard-mode | navigation actions over HTTP carry `EVENT_KEYPRESS` | **absent** | core:src/api/httpcontrol.c:234-258; go:internal/ui/glw/events.go:588-603 |
| H9 | shot | `/api/screenshot/raw`, `?raw=1\|true`: PNG; 5 s → 504; overlap → 502 | **same** | core:src/api/screenshot.c:71-162; go:internal/api/screenshot/screenshot.go:66-79 |
| H10 | shot | capture works once HTTP is up | **different**: early capture → 504, not replayed | go:docs/research/screenshot-api.md:119-121 |
| H11 | reload, preview | `GLW [ERROR]: Error f:l: msg` for *every* view load failure | **different**: parser/preproc errors only | core:src/ui/glw/glw_view.c:240-247,280-288; go:internal/ui/glw/glw_view.go:373-381,401-407 |
| H12 | reload --js, watch --js | ReloadData reloads `-p` plugins; logs `Reloaded dev plugin <p>` / `Unable to reload development plugin: <p>` | **absent** | core:src/navigator.c:863-874; core:src/plugins.c:1454-1471; go:internal/navigator/navigator_page.go:657-669 |
| H13 | reload --js | `Unable to compile <path> -- <msg>` | **same** | core:src/ecmascript/ecmascript.c:841; go:internal/ecmascript/ecmascript.go:1022 |
| H14 | health, keyboard | `global/userinterfaces/ui/{framerate,keyboard}` | **same** props | go:internal/ui/glw/root.go:266,504,657 |
| H15 | agent snapshot | `/api/diag` `<strong>movian</strong> Version X` | **different**: hard-coded `9.0.0` | go:cmd/movian-go/wire_network.go:345-353 |
| H16 | agent snapshot | `/api/ecmascript/stats`, `/gc` text | **same** format; memory ≠ JS heap | go:internal/ecmascript/es_stats.go:84-104; go:internal/ecmascript/ecmascript.go:724-727 |
| H17 | agent watch, stpp_probe | `/api/stpp` JSON `[1,sid,0,path]`, `[2,sid]`, `[3,0,path,v]`; notify `[4,…]` | **same** (ported, same constants) | core:src/api/stpp.h:23-37; go:internal/mgpp/mgpp.go:7-22; go:internal/api/mgpp/mgpp_cmd.go:173-214 |
| H18 | agent `--stpp`, stpp_probe | binary HELLO `00 03 00` → 19-byte `00 03 …` | **different**: [INFER] nil-pointer panic | go:cmd/movian-go/wire_network.go:423; go:internal/api/mgpp/mgpp_cmd.go:273 |
| H19 | agent `--stpp` | WebSocket `/api/ws/echo` | **absent** | core:src/api/httpcontrol.c:717-718; go:internal/api/httpcontrol/httpcontrol.go:457-481 |
| H20 | agent | `global/stpp/remoteControlled` counter | **same** | go:cmd/movian-go/wire_ui.go:121-123; go:cmd/movian-go/wire_network.go:392-404 |
| H21 | agent http-surface | `/api/logfile/<n>` serves the log the trace writes | **different** dir [INFER] | go:cmd/movian-go/wire_network.go:347; go:cmd/movian-go/wire_core.go:146 |
| H22 | agent http-surface | `/api/{done,openparameterized,input/utf8,notifyuser,image,static}`, `/favicon.ico` | **same** paths; `image` always 404, `notifyuser` drops msg | go:internal/api/httpcontrol/httpcontrol.go:138-171,420-428,462-476 |
| P1 | dev loop | `-p <dir>` loads; `Loaded dev plugin <path>` | **same** line; path raw, not normalised | core:src/plugins.c:1429-1440; go:cmd/movian-go/wire_network.go:113-121 |
| P2 | dev loop | JS hot reload | **absent** (H12); go:PLUGINS.md:153 claims auto-reload, no watcher found | go:PLUGINS.md:150-154 [MEASURED grep] |
| P3 | dev loop, LSP, canon | JS language = Duktape ES5.1 | **different**: goja, no syntax gate | go:README.md:38; go:internal/gaftape/gaftape_call.go:208 |
| P4 | preview, introspector | `--bypass-ecmascript-acl` honoured | **same** | go:internal/ecmascript/es_fs.go:54 |
| S1 | smoke | `needs.binary == "build.debug/movian"` | **different** | core:…/smoke.py:240-244 |
| S2 | smoke | health = nav trace + framerate + PNG | **different**: [INFER] fails on H2 | core:…/smoke.py:404-456 |
| S3 | smoke | example corpus `plugin_examples/{01-basic,02-intermediate,03-advanced,listx_cloner}` | **different**: 11 of 15 dirs absent in go: | [MEASURED §6] |
| X1 | x11 input | X11 window named exactly `Movian` | **different**: `Movian Go` / class `movian-go` | core:…/x11_keypress.py:35; go:internal/app/app.go:16,20 |
| X2 | x11 input | an X11 (XTest) window | **unknown**: GLFW picks X11 or Wayland; `--platform x11` pins | go:internal/ui/glw/glw_glfw.go:489-513 |
| T1 | types | generator over C sources → `generated/*` | **absent**: no emitter, no `generated/` | core:…/metadata/gen.py:9-35 [MEASURED] |
| T2 | types | native module surface | **different**: `fs` −4, `popup` +4, `+jambalaya` | [MEASURED §8] |
| T3 | types | JS module surface `res/ecmascript/**` | **different**: 17 of the files differ | [MEASURED §8] |
| T4 | types, LSP | GLW attribute/function/widget sets | **different**: attrs equal (116); functions −1; widgets −2 +1 | [MEASURED §8] |
| T5 | types | runtime oracle (api-introspector) | **unknown** | core:…/api-introspector/runtime-api-diff.md |
| LS1 | LSP | `build.debug/movian-analyze` (C GLW parser + Duktape) | **absent** | core:…/lsp/server.py:314; core:…/lspdoctor.py:146-150 |
| LS2 | LSP | `generated/movian-metadata.json`, `tests/tooling/lsp/*` | **absent** | core:…/lspdoctor.py:284-292,339-345 |
| LS3 | LSP | JS diagnostics source `duktape` | **different** semantics (P3) | core:…/lsp/server.py:29; core:…/lspdoctor.py:425-433 |
| O1 | preview | viewpreview plugin shipped in the core | **absent** in go:; its deps exist in code | core:…/harness.py:36; go:glwskins/flat/pages/raw.view |
| O2 | analyze | C analyzer over GLW + Duktape objects | **absent** | core:Makefile:1013-1029 |
| O3 | gdb | gdb lifecycle collector and wedge `gdb -p` | **absent**; Go analogue undocumented | core:…/smoke.py:795-801 |
| O4 | regression base | tracked tests in the core | **absent**: `*_test.go` gitignored, 0 tracked | go:.gitignore:68-69 [MEASURED] |
| O5 | skills | `$(mdev core)/…` path reach-ins in `plugins/**/*.md` | 25 reach-ins into C-only paths | [MEASURED §11] |

---

## 1. Locator and shim contract

**What the locator requires** (sdk:lib/locate.sh:166-207), in order:

- the root comes from `MOVIAN_CORE`, else `config.json .core`, else it fails hard (:169-186);
- the root is a directory (:188);
- `$root/support/devtools/mdev` exists (:193). If it does not, `movian_sdk_explain_missing_mdev`
  runs. It decides "is this Movian?" by `git cat-file -e HEAD:support/configure.inc` **and**
  `HEAD:src/prop/prop.h`, which are C build-system markers (:104-120);
- `$root/build.debug/movian` is executable (:198-203).

**What a movian-go checkout hits today** [MEASURED, `MOVIAN_CORE=/home/uzver/movian-go`]:

```
movian-sdk: core '/home/uzver/movian-go' (from MOVIAN_CORE) has no support/devtools/mdev.
  it is a git checkout, but not of Movian -- HEAD has no
  support/configure.inc + src/prop/prop.h.
  fix: point at a Movian checkout, not an unrelated directory.
```

`mdev core`, `mdev doctor` (which then also prints `locator: UNRESOLVED`) and `movian-lsp`
all exit 1 with this text. `mdev types` and `mdev viewdoc` take the same `movian_sdk_locate`
path (sdk:bin/mdev:43,86).

**Everything after the locator also assumes a C checkout:**

- **The hand-off.** `exec "$CORE/support/devtools/mdev"` (sdk:bin/mdev:250). The shim
  carries no execution logic of its own except `types`, `viewdoc` and `doctor`.
- **`types`.** It links `$CORE/generated/movian-api.d.ts`, whose "fix" hint names
  `support/devtools/metadata/gen.py` (sdk:bin/mdev:44,57-60).
- **`doctor`.**
  - `"$bin" --help | head -1` on `build.debug/movian` (:117-118). Against movian-go's binary
    this would read `Movian Go 0.0.0` [MEASURED].
  - Freshness from `find "$CORE/src" -name '*.c'` (:125). [INFER] For movian-go it would
    report "binary is newer than all C sources" vacuously, because `src/` does not exist and
    the error goes to `/dev/null`.
  - The `origin/movian6` distance (:132-135).
  - Nine `support/devtools/*` entries (:138-140).
  - The core's own `mdev lsp doctor` (:203).
- **`movian-lsp`.** It prefers `$PWD/support/devtools/movian-lsp`, then the located core's
  copy (sdk:bin/movian-lsp:16-18,34-35).
- **`install.sh`.** It refuses a core path without `support/devtools/mdev` (sdk:install.sh:100-104).

## 2. Build

| | C core | movian-go |
|---|---|---|
| recipe | `./support/configure-linux-debug.sh && make BUILD=debug -j$(nproc)` (sdk:lib/locate.sh:200) | `make ffmpeg` (one-off, "~15 min", go:BUILDING.md:62-64), then `make build` (go:Makefile:159-162) |
| binary | `build.debug/movian` (core:…/harness.py:31) | `./movian-go` in repo root (go:Makefile:162); `movian-go-bundle` for the embedded build (:477-480) |
| toolchain | C compiler + configure | Go 1.26 (go:go.mod:3), cgo |
| native deps | system libs via configure | static FFmpeg 9.0.1 in `./ffmpeg`, with `check-ffmpeg` refusing to build without it (go:Makefile:37ff); GLFW ≥ 3.4, where the vendored `third_party/glfw` shadows distro 3.3 (go:Makefile:133-139; go:BUILDING.md:46-50); CEF only if `pkg-config cef` (go:Makefile:129-131) |
| tags | n/a | `BUILD_TAGS ?= x11 glfw $(WEBPOPUP) $(CEF) $(EXTRA_TAGS)` (go:Makefile:147) |
| debug variant | `BUILD=debug` → `build.debug/` | none; plain `go build`. The existing binary has DWARF ("with debug_info, not stripped") [MEASURED `file`] |
| analyzer | `make BUILD=debug movian-analyze` (core:Makefile:1034-1049) | none: `cmd/` holds only `movian-go` [MEASURED] |

[MEASURED] On this machine `ffmpeg/lib/*.a` and `third_party/glfw/linux/lib/libglfw3.a`
exist, and `pkg-config cef` fails, so builds here carry no webpopup tag. The existing binary
links both `libX11.so.6` and `libwayland-client.so.0` (`ldd`).

## 3. Launch and lifecycle (`mdev run`, `stop`, `--force`)

**argv** (core:…/harness.py:348-368):

```
stdbuf -oL -eL ./build.debug/movian -d --disable-upgrades --persistent <dir> --cache <dir> [-p <abs>]… [--skin <abs>] [--libav-log] [--bypass-ecmascript-acl] [<url>]
```

The child is started with `cwd=REPO_ROOT`, `env += MOVIAN_MDEV_ALLOW_GDB=1`, stdout and
stderr both going to `/tmp/mdev/<name>/movian.log`, and `start_new_session=True`
(core:…/harness.py:381-389).

- **Flags.** Every flag above is parsed by go:cmd/movian-go/parseopts.go: `-d` :103, `--libav-log` :108,
  `--disable-upgrades` :154, `--skin` :199, `-p` :204, `--bypass-ecmascript-acl` :216,
  `--cache` :236, `--persistent` :241, and the first positional becomes the initial URL :305-308.
  Differences that mdev does not exercise:
  - `--help` omits `--disable-upgrades` and `--bypass-ecmascript-acl` [MEASURED];
  - `--ui` is removed (:246-249);
  - `--platform x11|wayland` is added (:250-261);
  - `-headless`/`--headless` is accepted as a no-op (:293-298);
  - an unknown flag stops parsing and becomes the URL (:300-302).
- **cwd / dataroot.** Go uses `./res` in the cwd, else the executable's directory
  (go:internal/app/dataroot.go:24-38). A cwd of the repo root satisfies it, as it does for C.
- **Readiness.** mdev scans the log for `http-server: Listening on port (\d+)` for 30 s
  (core:…/harness.py:38,393-429).
  - C emits that line from `asyncio_listen("http-server", …)`
    (core:src/networking/http_server.c:1166; core:src/networking/asyncio_posix.c:882).
  - movian-go's HTTP server is a separate `net.Listen(":42000")` that logs nothing on success
    (go:internal/networking/http/http_server.go:395-409; go:cmd/movian-go/wire_network.go:451).
  - The Go asyncio layer does have the same line (go:internal/asyncio/tcp.go:146-147), but
    only the FTP server uses it (go:internal/networking/ftpserver/ftp_server.go:852).
  - **[INFER]** `mdev run` against movian-go times out after 30 s and terminates the child.
- **Port.**
  - C binds 42000 with `bind_any=1` and falls back to port 0 if it is taken
    (core:src/networking/asyncio_posix.c:816-829). mdev's coexistence model rests on this
    ("isolated profile + dynamic port", core:…/cli.py:65-67).
  - Go binds 42000 only. On failure it traces `Failed to start HTTP control server` and runs
    on without HTTP (go:cmd/movian-go/wire_network.go:451,461-463). The STPP client also
    advertises a hard-coded 42000 (:495).
  - `movian_agent`'s default `--base-url` is already `http://127.0.0.1:42000`
    (core:…/movian_agent.py:549).
- **Process identity.**
  - `pid_is_movian` requires `/proc/<pid>/comm == "movian"` (core:…/harness.py:287-292).
  - `movian_procs` accepts a wrapper only if an argv token's basename is `movian`
    (:223-229).
  - `owns_pid` adds the `--persistent` path (:166-178). Everything addressed by instance
    (`live_pid`, `base_url`, `stop`) goes through it (:155-193).
  - **[INFER]** A `movian-go` process has comm `movian-go`, so `live_pid()` returns `None`.
    `base_url()` then raises "pid from state.json is dead", `stop` reports "not running", and
    foreign movian-go processes are invisible to the guard. To settle: launch one and read
    `/proc/<pid>/comm`.
- **Stop.** SIGTERM, then SIGKILL after 5 s, on the owned pid only (core:…/harness.py:295-323).
  movian-go installs SIGINT/SIGTERM handlers only via `arch.SetSignalHandler`, whose only
  caller is the sunxi UI (go:internal/arch/arch.go:644-652; go:cmd/movian-go/ui_glw_sunxi.go:33).
  **[INFER]** On desktop Linux, SIGTERM therefore kills the process by Go's default action,
  with no shutdown hooks. mdev sees "stopped-clean" either way.
- **gdb opt-in.** C calls `prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY)` when
  `MOVIAN_MDEV_ALLOW_GDB=1` (core:src/arch/linux/linux_misc.c:156-165). There is no
  equivalent in go: [MEASURED grep].
- **`--dev-flags`.** It writes JSON to `<persistent>/settings/dev` (core:…/cli.py:73-79).
  Go's dev settings use store key `("dev", id)` (go:internal/settings/dev/devsettings.go:48-72),
  as C does (core:src/settings.c:1500). Runtime unverified.
- **Log format.** Go's trace prefix is `fmt.Sprintf("%-15s [%-5s]:", subsys, leveltxt)`
  (go:internal/trace/trace.go:182), the same as C. The stderr copy goes through `log.Printf`
  (:212-214), so it carries Go's default date/time prefix (`log.SetFlags` is called only in
  go:cmd/movian-go/android_jni.go:355). mdev's regexes are unanchored. The on-disk log is
  `<cache>/log/movian-0.log` (go:internal/trace/trace.go:86-97; go:cmd/movian-go/wire_core.go:146).
  Both go:PLUGINS.md:156 and go:USER_GUIDE.md:92 say `log/movian-go-0.log`.

## 4. Remote-control surface

### 4.1 Which command depends on what

| command | core checkout | running instance |
|---|---|---|
| `run` | `build.debug/movian`, cwd | flags (R1), port line (R3), comm (R5) |
| `stop` | — | comm + cmdline in `/proc` (R5) |
| `open` | — | `/api/prop` ×n, `/api/open`, **nav `Opening` trace** (core:…/harness.py:545-645) |
| `shot` | — | `/api/screenshot/raw` (core:…/harness.py:860-897) |
| `props` | — | `/api/prop` (core:…/cli.py:163-205) |
| `log` | — | the stdout/stderr file `run` wrote (core:…/cli.py:212-232) |
| `reload` | — | `POST /api/input/action/ReloadUI` → GLW, `GLW [ERROR]` lines (core:…/harness.py:730-751) |
| `reload --js` | — | `POST …/ReloadData` → dev-plugin reload lines (core:…/harness.py:769-847) |
| `watch` | default dir `<core>/glwskins/flat` (core:…/cli.py:349) | the `reload` flows above |
| `preview` | `<core>/support/devtools/viewpreview` (core:…/harness.py:36) | ReloadUI flush, `open`, `viewpreview: ERROR:` / `GLW [ERROR]` lines (core:…/cli.py:479-556) |
| `smoke` | `<core>/support/devtools/smokes`, `needs.binary` | all of the above + `ui/framerate` |
| `lsp doctor`, `movian-lsp` | `build.debug/movian-analyze`, `generated/movian-metadata.json`, `tests/tooling/lsp/`, `Makefile`, `metadata/gen.py` | — |
| `types`, `viewdoc` | `generated/*` | — |
| `movian_agent.*`, `movian_diag_snapshot`, `stpp_probe` | run *from* `<core>/support/devtools` as modules | HTTP, STPP, WS only (`--base-url`) |
| `x11_keypress`, `x11_pointer` | — | X11 window by name |

### 4.2 Endpoint by endpoint

- **`/api/open`.**
  - C: `event_to_ui(event_create_openurl(url))` then a redirect to `/api/open`
    (core:src/api/httpcontrol.c:50-65).
  - Go: `navSys.Open(url, "")` then the same redirect (go:internal/api/httpcontrol/httpcontrol.go:59-85;
    go:cmd/movian-go/wire_network.go:357-363). It reaches `navOpen0` directly
    (go:internal/navigator/navigator_open.go:202-231).
  - Same shape.
- **The navigator trace.**
  - `open_and_wait` will not trust the prop tree until the log shows
    `navigator.*Opening (\S+)` equal to the requested URL (core:…/harness.py:72-76,566-581).
    The health smoke requires the same trace (core:…/smoke.py:422-424).
  - C emits it in `nav_open0` (core:src/navigator.c:763). Go's `navOpen0` has no trace
    (go:internal/navigator/navigator_open.go:315-346).
  - The only "Opening" lines in go: are `es_route.go:211` (`Opening route <pattern>`, debug,
    plugin subsystem) and an unrelated set [MEASURED grep]. Neither matches.
  - **[INFER]** `mdev open` and `mdev preview` time out after 20 s with `nav_event_seen=False`.
- **Page props.** `currentpage`, `canGoBack`, `canGoForward`, `canGoHome`, `eventSink`
  (go:internal/navigator/navigator_open.go:168-174), `model/loading` (:255) and
  `type="openerror"` (go:internal/backend/core/fileaccess_backend.go:537-542) use the same
  names that mdev reads (core:…/harness.py:86-95; core:…/movian_agent.py:28-41).
- **`/api/prop`.**
  - The text body is ported line for line: `name (ref:N xref:N) is a …`, `directory`, two-space
    child names, `<unnamed>`, `(void)`/`(zombie)` (go:internal/prop/http/prop_http.go:125-175 against
    core:src/prop/prop_http.c:147-238). That is what `parse_prop` reads
    (core:…/movian_diag_snapshot.py:34-71).
  - **The lookup differs.**
    - C `prop_from_path` uses `prop_findv`, which never creates
      (core:src/prop/prop_http.c:29-33; core:src/prop/prop_core.c:5049-5091). The fork fixed
      this in "issue-152-prop-http-index" (core git `f2c88eb08`, `35a35390a`).
    - Go uses `GetByName` → `Subfind`, which creates any missing child
      (`pm.CreateEx(p, name, …)`, go:internal/prop/prop_registry.go:233-236) and converts a
      VOID parent to a directory (:181-199).
    - **[INFER]** In Go a missing path answers 200 `(void)` instead of 404, and the GET leaves
      the prop behind. `mdev props` then prints a value where C says "not found". The smoke
      `absent: true` still passes, because `(void)` coerces to `None`
      (core:…/smoke.py:253-262).
  - POST `debug`/`action` are the same (go:internal/prop/http/prop_http.go:105-123).
- **`/api/input/action/<A>`.**
  - C: `event_to_ui(e)`, which sends the event to `global.userinterfaces.ui.eventSink`, i.e.
    GLW. It sets `EVENT_KEYPRESS` on up/down/left/right/activate/back/focus/page/top/bottom,
    with a comment saying this is so tooling engages keyboard mode
    (core:src/api/httpcontrol.c:227-261).
  - Go: `h.eventMgr.Dispatch(h.eventMgr.CreateActionStr(remain))`
    (go:internal/api/httpcontrol/httpcontrol.go:94-107). `Dispatch` is the port of C
    `event_dispatch`. It feeds `global.eventSink` and the nav, volume and media sinks
    (go:internal/event/event.go:983-1070).
  - GLW subscribes to `ui.eventSink` (go:internal/ui/glw/root.go:318). The subscribers of
    `global.eventSink` are runcontrol (go:internal/runcontrol/runcontrol.go:86-89) and a
    handler that acts only on `ACTION_SWITCH_UI` (go:internal/arch/linux_main.go:114-144).
  - Go *has* `EventToUI` (go:internal/event/event.go:1130-1140), but httpcontrol does not call it.
  - **[INFER]**
    - `ReloadUI` and arrow actions posted over HTTP never reach GLW. That covers the plain
      `reload`, the preview flush and the smoke `action` verb.
    - `ReloadData` does reach the navigator through the nav-event branch.
    - Keyboard mode needs `EventKeypress` (go:internal/ui/glw/events.go:588-603), and nothing
      in httpcontrol sets it.
    - To settle: post `ReloadUI` with a deliberately broken `.view` and grep the log. Then
      post `down` twice and read `global/userinterfaces/ui/keyboard`.
  - `movian_agent action` uses GET (core:…/movian_agent.py:482-489), while mdev and the smokes
    use POST (core:…/harness.py:737; core:…/smoke.py:369). Both handlers ignore the method.
- **`/api/screenshot`.**
  - Same contract: `/raw`, `?raw=1`, `?raw=true` → PNG; 5 s → 504; concurrent → 502; plain →
    Imgur JPEG + 302 (go:internal/api/screenshot/screenshot.go:66-79,338-342;
    go:docs/research/screenshot-api.md:22-29; core:src/api/screenshot.c:71-162).
  - movian-go's own research note names mdev's `take_shot` as the consumer it designed for
    (go:docs/research/screenshot-api.md:17,31).
  - Its runtime note: *"The HTTP listener comes up before the UI event subscription; sending a
    capture event before that subscription exists does not replay it … HTTP readiness is
    therefore not sufficient proof of GLW readiness"*, with an observed 504 after 5.037 s
    (go:docs/research/screenshot-api.md:119-121).
- **GLW error lines.**
  - mdev matches `GLW\s+\[ERROR\]:\s*Error (.+?):(\d+): (.*)$` (core:…/harness.py:42).
  - C traces at `glw_view_seterr` and also at the load convergence point, for file-open,
    lexer and `#include`/`#import` failures that bypass `seterr`
    (core:src/ui/glw/glw_view.c:240-247,280-288).
  - Go traces only in `glwViewSeterr` (go:internal/ui/glw/glw_view_support.go:95). The open and
    lexer failure paths store `gcvError` without tracing (go:internal/ui/glw/glw_view.go:373-381,401-407).
  - **[INFER]** A missing view file or a lexer error gives a clean `RELOAD OK` or `PREVIEW`
    on movian-go: a false green.
- **Dev-plugin reload (`ReloadData`).**
  - C: `nav_reload_current` → `plugins_reload_dev_plugin()` → per path
    `Reloaded dev plugin %s` or `Unable to reload development plugin: %s\n%s`
    (core:src/navigator.c:863-874; core:src/plugins.c:1454-1471).
  - Go: `navReloadCurrent` only reloads the page (go:internal/navigator/navigator_page.go:657-669).
  - `plugins.ReloadDevPlugin` exists but has no caller [MEASURED grep]. It iterates
    `pm.devPlugins`, and that is empty: `plugins.Start(…, nil)` (go:cmd/movian-go/wire_network.go:101;
    go:internal/plugins/plugin_init.go:23,116-138).
  - Its lines are also worded differently: `Reloaded dev plugin: %s` (colon, :135) does not
    match `Reloaded dev plugin (\S+)` (core:…/harness.py:51), and the failure text is
    `Failed to reload dev plugin` (:133).
  - A second, unbuilt `ReloadDevPlugin` stub sits behind `//go:build reference`
    (go:internal/plugins/plugins.go:1,92-100).
  - **[INFER]** `mdev reload --js` reports `no reload result seen` for every plugin and exits 1.
- **Compile errors.** `Unable to compile %s -- %s` is the same
  (go:internal/ecmascript/ecmascript.go:1022; core:src/ecmascript/ecmascript.c:841).
- **`/api/diag`.** The handler is constructed with `"movian"`, `"9.0.0"`
  (go:cmd/movian-go/wire_network.go:345-353; go:internal/api/httpcontrol/httpcontrol.go:177-182).
  The agent's version regex matches, but the value is constant.
- **`/api/ecmascript/stats`.**
  - Same text layout (go:internal/ecmascript/es_stats.go:84-104,160-161).
  - The memory figures count only allocations routed through the heap shim: *"Go can't hook
    goja allocations"* (go:internal/ecmascript/ecmascript.go:724-727). The before/after deltas
    in `movian_diag_snapshot --gc` mean something different from what they mean on Duktape.
- **STPP.**
  - The wire constants are equal (core:src/api/stpp.h:23-37; go:internal/mgpp/mgpp.go:7-22).
  - The JSON subscribe, unsubscribe and set handlers are ported
    (go:internal/api/mgpp/mgpp_cmd.go:173-214; go:internal/api/mgpp/mgpp_subjson.go cites stpp.c lines).
  - Binary frames are dispatched with `MgppHandleBinary(apiMgpp, nil, …)`
    (go:cmd/movian-go/wire_network.go:423). HELLO reaches `MgppSendHello(mgpp, client)`, which
    reads `client.instanceID` (go:internal/api/mgpp/mgpp_cmd.go:263-273,482).
  - There is no `recover()` in `internal/networking`, `internal/api` (except the screenshot
    goroutine) or `cmd/` [MEASURED grep].
  - **[INFER]** `stpp_probe --binary-hello` or `movian_agent snapshot --stpp|--full` crashes
    movian-go with a nil-pointer panic. To settle: send the HELLO to a throwaway instance.
  - `/api/mgpp` is a Go alias of `/api/stpp` (go:cmd/movian-go/wire_network.go:383).
- **`/api/ws/echo`.** C registers it (core:src/api/httpcontrol.c:717-718). It is not in Go's
  `Register` (go:internal/api/httpcontrol/httpcontrol.go:457-481) and appears nowhere in go:
  [MEASURED grep].
- **`/api/logfile`.** Go's handler reads `<persistent>/cache/log/movian-N.log`
  (go:cmd/movian-go/wire_network.go:347; go:internal/api/httpcontrol/httpcontrol.go:187-192,232).
  The trace writes `<--cache>/log/movian-0.log` (go:cmd/movian-go/wire_core.go:146).
  **[INFER]** Under mdev's split `--cache`/`--persistent`, the endpoint serves nothing.
- **Auth.** Go's `checkAuth` passes when `authToken` is empty, and `SetAuthToken` has no
  caller (go:internal/api/httpcontrol/httpcontrol.go:354-357,403-416). It is open, as in C.
- **Prop paths read by the agent and smokes** all have Go creators:
  - `userinterfaces/ui/{framerate,keyboard}` (go:internal/ui/glw/root.go:266,504,657)
  - `stpp/remoteControlled` (go:cmd/movian-go/wire_ui.go:121-123)
  - `popups` (go:internal/notifications/notifications.go:239-240)
  - `app/systemname` (go:internal/settings/settings_manager.go:300)

## 5. Plugin dev loop

- **Sideload.** `-p` → `pluginManager.LoadPlugin(path, "dev", Force|ByUser)` → `Loaded dev
  plugin %s` (go:cmd/movian-go/wire_network.go:113-121).
  - C normalises the path with `fa_normalize` and loads with `FORCE|DEBUG`
    (core:src/plugins.c:1429-1440).
  - mdev already tolerates both a `file://` and a plain path when it matches reload lines
    (core:…/harness.py:706-723).
  - `PluginLoadDebug` gates `ECMAScriptDebug` (go:internal/plugins/plugin_loader.go:164-167),
    so Go dev plugins load without the debug flag that C sets.
  - The plugin FQID is `<id>@dev` (go:internal/plugins/plugin_manager.go:459). That is the
    shape example-smokes address (`plugin:example_listx_cloner@dev`).
- **Hot reload.** Absent (§4.2). go:PLUGINS.md:150-154 says *"the dev plugin auto-reloads
  when its files change"*. A grep of `internal/plugins`, `internal/ecmascript` and `cmd/` for
  fsnotify, inotify, watcher, ModTime and auto-reload finds nothing, and `fsnotify` is not
  in go.mod [MEASURED].
- **Engine.**
  - `gaftape` is *"the Duktape C API surface … implemented over goja"*
    (go:internal/gaftape/gaftape_conv.go:1-5).
  - Scripts compile through `goja.Compile(name, src, false)` with no language-level gate
    (go:internal/gaftape/gaftape_call.go:208; go:internal/gaftape/gaftape_ctx.go:382).
  - go:README.md:38 states "goja — broader ECMAScript support".
  - **[INFER]** ES2015+ syntax that Duktape rejects with `SyntaxError` loads on movian-go.
    A plugin can be green on one core and fail to load on the other, in either direction for
    library methods. To settle: load a fixture with an arrow function on both.
  - A global `print` exists (go:internal/gaftape/gaftape_ctx.go:211-236).
- **ACL.** `--bypass-ecmascript-acl` → `gconf.BypassEcmascriptACL`, which is read in
  go:internal/ecmascript/es_fs.go:54.

## 6. Smokes

Discovery: the core `smokes/`, then `MOVIAN_SMOKES_PATH`, then `./.movian/smokes`
(core:…/smoke.py:134-164).

The binary gate: `needs.binary` must equal `build.debug/movian` exactly, or the run refuses
with "requests unsupported binary" (core:…/smoke.py:240-244).

Each core smoke and what it assumes:

| smoke | assumes | movian-go [INFER] |
|---|---|---|
| `health` | nav `Opening` trace in log + `ui/framerate` value + PNG from `/raw` within 20 s (core:…/smoke.py:404-456) | fails on the trace (H2) |
| `open-home` | `page:home` opens; log matches `navigator.*Opening\s+page:home`; `loading ∈ {0,null}`; title present | fails (H2) |
| `preview-demo`, `preview-pilot` | `<core>/support/devtools/viewpreview` plugin, ReloadUI flush, 12/10 nodes, `nodes/*0/url`, title `Укрытие`, no `GLW [ERROR]`/`viewpreview: ERROR:` | plugin absent from go:; H2, H7 |
| `reload-clean` | ReloadUI produces no `GLW [ERROR]` | vacuous pass if H7 holds |
| `keyboard-mode` | `ui/keyboard ∈ {0,null}`, `POST action down ×2`, then `keyboard == 1` | fails (H7, H8) |
| `js-reload` | preview, then ReloadData with per-plugin reload lines | fails (H12) |

**Example smokes** (`core:support/devtools/example-smokes/*.json`) resolve
`../../../plugin_examples/<dir>` against their own directory (core:…/smoke.py:212-235). They
assert route titles and node counts, plus two settings paths
(`global/settings/apps/nodes/examples.*/nodes`) and one service path. [MEASURED] Of the 15
plugin dirs they name, movian-go's `plugin_examples/` has 4 (`async_page_load`, `music`,
`subscriptions`, `webpopupplugin`). The missing 11 are everything under `01-basic`,
`02-intermediate` and `03-advanced`, plus `listx_cloner`.

## 7. X11 input

- **The tools.**
  - `x11_keypress.py` and `x11_pointer.py` load `libX11` and `libXtst` through ctypes
    (core:…/x11_common.py:9-26).
  - They open `$DISPLAY` (default `:0`) and BFS the window tree for a window whose
    `XFetchName` **equals** `--window`, default `"Movian"`
    (core:…/x11_keypress.py:35-46; core:…/x11_pointer.py:71-72; core:…/x11_common.py:133-140).
  - They then use XTest key, motion and button events.
- **The C window title.** `APPNAMEUSER`, which is `"Movian"` in this build
  (core:build.debug/config.h:6 [MEASURED]), set at core:src/ui/glw/glw_x11.c:357-358.
- **movian-go.**
  - GLFW creates the window titled `AppNameUser = "Movian Go"`, with X11 class/instance and
    Wayland app_id `AppName = "movian-go"` (go:internal/app/app.go:16,20;
    go:internal/ui/glw/glw_glfw.go:105-113,300-304).
  - **The default `--window Movian` does not match.**
- **Platform.**
  - GLFW_ANY "picks Wayland/X11 from XDG_SESSION_TYPE". `GLFW_PLATFORM` env or
    `--platform` pins it, and an X11 retry happens only when the first `glfwInit` fails
    (go:internal/ui/glw/glw_glfw.go:489-513).
  - [MEASURED] This WSLg host has `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0` and no
    `XDG_SESSION_TYPE`.
  - **unknown** Which platform an unpinned launch picks here. If it picks Wayland, XTest
    cannot reach the window. To settle: launch with `-d` and inspect `xwininfo -root -tree`.
  - movian-go's own screenshot smoke ran "with … X11" (go:docs/research/screenshot-api.md:125).

## 8. Types and metadata

**How the C artifact is made.** `core:support/devtools/metadata/gen.py` (6450 lines,
stdlib only) writes three files: `generated/movian-metadata.json`, `movian-api.d.ts` and
`movian-api-v1.d.ts` (:66-75). It reads:

- `attribtab[]` in `src/ui/glw/glw_view_attrib.c`, `funcvec[]` in `glw_view_eval.c`, and
  every `glw_class_t` in `src/ui/glw/glw_*.c` (:9-22,409-413);
- `ES_MODULE(...)` and `duk_function_list_entry` tables in `src/ecmascript/es_*.c`, with
  argument types inferred from `duk_require_*`, `duk_to_*`, `duk_get_*` and `duk_push_*`
  in the C bodies (:25-27,433-434,851-1036);
- CommonJS exports and prototypes in `res/ecmascript/modules/**/*.js` (:27-28). These files
  carry type annotations added in the fork (core git `0dbab7880` "core modules: annotate what
  the gate could not see (#212)");
- curated JSON: operators, scopes, plugin manifest, interpreter globals and objects
  (:415-421);
- `git rev-parse HEAD` as `movianRevision` (:40-44).

It cross-checks against a **runtime oracle**, `api-introspector/runtime-api.json`, and
stamps that oracle's inputs (:76-120).

The introspector is an apiversion-1 ES5 plugin (core:…/api-introspector/plugin.json:1-6).
- It `require`s 52 module ids, a fixed list plus every file found by walking
  `dataroot://res/ecmascript/modules` (introspector.js:13-147).
- It records `Object.keys` and one prototype level, calls `movian/settings.globalSettings`,
  and registers route `introspect:page`.
- It `print`s a `MOVIAN_API_INTROSPECTOR_JSON=` marker that is extracted from the log
  (introspector.js:952,1012-1024,1201-1219; runtime-api-diff.md:3-11).
- It needs `--bypass-ecmascript-acl` to walk the module tree (core:…/cli.py:657-664).

**movian-go has no equivalent output.** It has no `generated/` directory. The repo contains
no `d.ts`, `movian-api`, `movian-metadata` or `introspect`; the only hits are D-Bus
introspection in mpris/upnp [MEASURED].

The structures that would be a Go source of truth do exist, in Go form:

- `var attribtab = []tokenAttrib{…}` (go:internal/ui/glw/glw_view_attrib.go:288-289);
- `var funcvec = []tokenFunc{…}` (go:internal/ui/glw/glw_view_eval_funcs.go:1659);
- `gcName:` fields on widget classes;
- `[]gaftape.FunctionListEntry{Key, Value, Nargs}` tables registered by
  `EcmascriptRegisterModule(&EcmascriptModule{Name, Functions})`
  (go:internal/ecmascript/es_fs.go:293-312; go:internal/ecmascript/register_modules.go:8-37).

Native bodies call `ctx.ToString(i)` and similar, mirroring the `duk_*` readers
(go:internal/ecmascript/es_fs.go:52,85).

**How far the surfaces have drifted** [MEASURED, regex over both trees]:

- **Native modules.** C registers 18 and Go registers 19, the same 18 plus `jambalaya`.
  - `native/fs`: C has `ftruncate`, `unlink`, `rmdir` and `readdir`, and Go does not
    (core:src/ecmascript/es_fs.c:468-484 against go:internal/ecmascript/es_fs.go:293-304).
  - `native/popup`: Go adds `webbrowser`, `webcookies`, `webuseragent` and `injectcookies`
    (go:internal/ecmascript/es_misc.go:378-382 against core:src/ecmascript/es_misc.c:327-335).
  - The other 16 shared modules have equal function sets.
  - **Every shared function has equal `nargs`** (0 mismatches).
- **JS modules.** `diff -rq res/ecmascript` lists 17 differing files
  (37 insertions, 275 deletions from C to Go). Most of the deletions are C-fork JSDoc. The
  differences that change behaviour:
  - Go's `fs.js` lacks `readdirSync`, `unlinkSync`, `mkdirSync` and `rmdirSync`, and its
    `readFileSync` returns a decoded string;
  - `movian/html.js` lacks the `getElementsByClassName` and `getElementsByTagName` aliases;
  - `legacy/api-v1.js` lacks `print: print`;
  - `movian/settings.js` stringifies kvstore URLs;
  - `xml.js` branches on `Duktape.version`.
- **GLW** (against `core:generated/movian-metadata.json`, `movianRevision 0dbab78`):
  - attributes: 116 in each, identical;
  - functions: C 90, Go 89 (`dumpDynamicStatements` missing);
  - widgets: C-registered `fader` and `stencil` are absent in Go (core:src/ui/glw/glw_clip.c:292,495);
    Go adds `websurface` (go:internal/ui/glw/glw_websurface.go:79).
- **Docs against code in movian-go.** go:PLUGINS.md:99-124 lists seven `native/*` names that
  no `EcmascriptRegisterModule` call registers: `timer`, `scrobble`, `stats`, `console`,
  `searcher`, `itemhook`, and `subtitles` (the registered name is `subtitle`) [MEASURED].
  `webpopup` already exists in the C fork (core:src/ecmascript/es_misc.c:327). The new API
  surface is the four extra `popup` functions and Go's CEF backend
  (go:PLUGINS.md:129-145, a stub without `cef.pc`).

**T5 (unknown).** It is not known whether `api-introspector` runs on movian-go. Its
prerequisites exist in Go code: apiversion-1 bootstrap, `print`, `dataroot://` walk, ACL
bypass and `movian/page` Route. Its comments and marker logic assume Duktape
(introspector.js:3). To settle: `mdev run -p …/api-introspector --bypass-ecmascript-acl`
against movian-go, open `introspect:page`, and diff the captured payload.

## 9. LSP

- **The server** (core:support/devtools/lsp/server.py, 1650 lines) roots itself at
  `parents[3]` of its own file (:312). It needs:
  - `build.debug/movian-analyze` (:314), for GLW `--check`/`--tokens` and for JS
    `--js` (:710);
  - `glwskins/flat` (:315);
  - `generated/movian-metadata.json` (:316).
- **JS diagnostics** are tagged `duktape` (:29).
- **`lspdoctor.py`** checks:
  - Python ≥ 3.10;
  - analyzer freshness, by parsing the core `Makefile`'s `MOVIAN_ANALYZE_*_OBJS` and the
    `.d` depfiles (:146-245);
  - `gen.py --check` (:247-281);
  - an LSP initialize round-trip using `tests/tooling/lsp/lsp_client.py` (:284-337);
  - widget completion against the metadata (:339-400);
  - a JS probe that **expects an arrow function to be a Duktape error** (:402-476, fixture at :425-433).
- **The analyzer** links the real C lexer, preproc, parser, support, attrib and eval objects
  plus `ext/duktape/duktape.o` (core:Makefile:1013-1029).
- **movian-go** has none of these files.
  - Its GLW lexer and parser are Go (`internal/ui/glw/glw_view_lexer.go`, `…_parser.go`)
    with no CLI entry.
  - **[INFER]** The JS probe's premise (ES6 is an error) is false for the goja runtime (§5).

## 10. viewpreview, analyze, gdb

- **viewpreview** (core:support/devtools/viewpreview):
  - an apiversion-2 dev plugin with route `viewpreview:show:<base64 JSON>`;
  - it reads view and fixture files with `native/fs` and `fs.readFileSync`, and sets
    `type='raw'` and `metadata.glwview` (viewpreview.js:23-61,88,96,140);
  - it needs the core flag `--bypass-ecmascript-acl` (core:…/harness.py:452-473).
  - Go has the modules, `raw.view` (go:glwskins/flat/pages/raw.view) and the flag. Whether
    the plugin runs on Go is **unknown**, and the plugin itself ships only in the C core.
- **analyze.** A host CLI driving the real C GLW lexer, preproc and parser and Duktape
  (core:support/devtools/analyze/movian_analyze.c:1-40). It is C-specific. Go has no
  counterpart.
- **gdb.**
  - `movian_lifecycle.py` launches the inferior under GDB with C-function breakpoints from
    `inventory.json`, and records pid and port into mdev's `state.json`
    (core:support/devtools/gdb/movian_lifecycle.py:1-24).
  - Smoke wedge capture runs `gdb --batch -p <pid> -ex "thread apply all bt"`, or uses a
    launch-attached GDB (core:…/smoke.py:758-839), relying on `PR_SET_PTRACER` (R7).
  - movian-go documents no delve or pprof workflow [MEASURED grep for delve, dlv and pprof
    across `*.md`, `*.go` and the Makefile]. The only debugging evidence is a "SIGQUIT dump
    of the owned test process" (go:docs/research/screenshot-api.md:119).
  - Go analogue: **unknown**.

## 11. Couplings outside the core

- **Skills reach past the shim.** `plugins/**/*.md` contain 25 `$(mdev core)/…`
  references into C-only paths [MEASURED]:
  - `support/devtools` ×6
  - `build.debug/movian` ×4
  - `generated/movian-api.d.ts` ×3
  - `plugin_examples/` ×2
  - one each: `support/devtools/viewpreview/`, `…/metadata/gen.py`,
    `…/mdevlib/x11_keypress.py`, `glwskins/flat`, `docs/Guides/PLUGIN_API_REFERENCE.md`,
    `build.debug/movian-analyze`, `build.debug/config.mak`

  Examples: sdk:plugins/movian/skills/run/SKILL.md:99 runs `movian_agent` from
  `$(mdev core)/support/devtools`, and sdk:plugins/movian/skills/view/SKILL.md:201 calls
  `build.debug/movian-analyze` directly.
- **movian-go has no tracked tests.** `.gitignore:68-69` ignores `*_test.go`, and
  `git ls-files | grep -c _test.go` returns 0 [MEASURED]. Its screenshot regressions exist
  only in the local tree (go:docs/research/screenshot-api.md:165).
- **movian-go's C reference is mixed.** Code comments cite C line numbers, for example
  `main.c:523-717` (go:cmd/movian-go/parseopts.go:3). The screenshot note cites
  `Buksa/movian` `movian6` and the mdev harness by URL (go:docs/research/screenshot-api.md:11,17).
  Fork-only C changes that mdev depends on are not in Go:
  - KEYPRESS on HTTP actions (H8);
  - non-creating prop lookup (H5);
  - convergence-point GLW error trace (H11).

---

## Open questions

The decisions these facts force. Each is stated as a question only.

1. **Where an execution layer for a Go core would live.**
   - The C layer is ~4.9 k lines of in-core Python plus a plugin, smokes and an analyzer,
     resolved relative to the core's own file (`REPO_ROOT = parents[3]`).
   - movian-go has no `support/`, no Python tooling and no tracked tests.
   - Does a Go-core layer live in movian-go, in this SDK, or split between them, and who
     owns its regexes?
2. **Core kinds in the locator.**
   - Does the one-designated-core contract (`MOVIAN_CORE` → `config.json` → hard fail) learn
     about core kinds, or about two designated cores?
   - What marker identifies a Go core?
   - What should `movian_sdk_explain_missing_mdev` call a Movian port that has no C build
     markers?
3. **Protocol-only against build-bound commands.**
   - Protocol-only: `open`, `shot`, `props`, `log`, `reload`, `watch`, `movian_agent`,
     `stpp_probe` and the X11 tools need only a base URL, a log path and a pid.
   - Build-bound: `run`, `doctor`, `lsp`, `types`, `viewdoc`, and `smoke` through
     `needs.binary`, which name C files.
   - Is that split the seam, and which side does `preview` (a plugin shipped in the core) fall on?
4. **Readiness.** What readiness contract must a core meet: a specific log line, a port the
   harness chooses, or an HTTP probe? movian-go's own note says HTTP-up does not mean GLW-ready.
5. **Port.** Does mdev's coexistence model (dynamic port) survive a core that binds a fixed
   42000? Is a port option a core change, or a harness constraint of one instance at a time?
6. **Process identity.** Should ownership be proved by binary name (`comm == movian`), or by
   the launch handle and `--persistent` path alone?
7. **Who keeps the proof signals in step across cores.** mdev's proofs are log lines and side
   effects added to the C fork for tooling: the nav `Opening` trace, the reload lines, the
   GLW convergence trace and KEYPRESS on HTTP actions. Is that contract written down anywhere
   other than mdev's regexes? Who adds it to movian-go?
8. **HTTP action semantics.** Is `/api/input/action` defined as "to the UI" (`event_to_ui`)
   or as "dispatch" (`event_dispatch`)? Does `/api/prop` GET on a missing path create the prop?
9. **Which C movian-go tracks.** Does movian-go follow upstream C or the `movian6` fork? Are
   fork fixes that tooling depends on (issue-152, the KEYPRESS change) in scope for it?
10. **Source of truth for movian-go's plugin API.** Is it Go's function-list tables, a
    runtime introspector capture, or the C artifact plus a delta? Is the plugin API one
    contract both cores conform to, or two diverging ones (`fs` −4, `popup` +4, GLW widgets −2 +1)?
11. **What `mdev types` hands an author.** One artifact for the intersection, one per core
    kind, or the designated core's own?
12. **Language level.** What language level does the SDK canon promise plugins (Duktape ES5.1
    or goja's), and which runtime does `movian-lsp`'s JS diagnostic emulate?
13. **GLW tooling across divergent cores.** `movian-analyze`, the LSP and `viewdoc` are built
    from one core's parser and tables. Which core, now that the widget sets differ?
14. **Smokes.** Are smoke definitions portable across cores (`needs.binary`, prop paths, log
    patterns) or per core? Which repo owns the `plugin_examples` corpus the example smokes run?
15. **X11 input.** Is the window name a parameter, a per-core constant, or something to
    unify? Does a Go launch pin `--platform x11` so XTest works?
16. **Wedge and crash capture for Go.** gdb `-p`, the Go runtime's SIGQUIT dump, or delve?
    None is documented in movian-go.
17. **movian-go's docs against its code.** On the module list, log path and dev-plugin
    auto-reload, PLUGINS.md and USER_GUIDE.md disagree with the code. Which one does the SDK
    canon cite?
