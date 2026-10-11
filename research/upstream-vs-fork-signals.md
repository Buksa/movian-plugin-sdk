# Which tooling signals are upstream C, and which are movian6-only

> **Point-in-time survey. Measure again before acting on it.**
> Investigated on the date stated below against the refs named in Sources. All three
> trees move, and their line numbers go stale first. **Nothing was built or launched,
> and nothing was fetched.** Every statement about what movian-go does at *runtime*
> comes from reading its code or from the gap inventory, and is marked **[INFER]**
> wherever it predicts an outcome. No corrections have been found against this file.

Research for [issue #48 "Which tooling signals are upstream C, and which are movian6-only?"](https://github.com/Buksa/movian-plugin-sdk/issues/48),
part of the wayfinder map [issue #46 "Wayfinder: mdev across two cores"](https://github.com/Buksa/movian-plugin-sdk/issues/46).
Investigated 2026-10-11.

**Sources.** Citation prefixes name the tree; `mdevlib/` is short for
`fork:support/devtools/mdevlib/`.

- **[READ]** — read-only reading with `git show`, `git grep` and `git log -S/-G`, cited
  `prefix:path:line`.
  - `up:` andoma/movian `master`, the remote-tracking ref `upstream/master` @ `65c22dd27`
    (2019-01-13) in `/home/uzver/movian-public-clean`. The merge-base with the fork is
    `66c8ad8a60`, one commit behind it.
  - `up6:` andoma/movian's **own `movian6` branch**, `upstream/movian6` @ `4b5b6d781`
    (2019-01-13). It is `up:` plus 27 commits, all by Andreas Smas. Buksa's `movian6` is
    `up6:` plus 466 commits: `git log HEAD..upstream/movian6` is empty. For every
    signal-bearing file except `src/plugins.c` and `src/main.c`, `git diff upstream/master
    upstream/movian6` is empty.
  - `fork:` Buksa/movian `movian6` @ `593627edd`, read as `HEAD:` and **not** from the
    working tree (see the note below).
  - `go:` `/home/uzver/movian-go` @ `10775f3`. That is the local branch
    `wip/translation-upload-route-local`, which is on no remote; its parent is `9db952e`.
  - `czz:` czz/movian-go `master`, the ref `upstream/master` @ `d761987` in the same clone.
    It has 34 commits that `go:` lacks. Every movian-go gap that routes to an issue or a PR
    was re-checked there.
  - `gap:` the gap inventory, `research/movian-go-mdev-gap.md` on branch
    `research/movian-go-mdev-gap` of this repo, cited by its row id (`R3`, `H5`, …).
- **[INFER]** — the conclusion follows from the cited code but was not observed. Each one
  names what would settle it.

**The fork checkout's index is not HEAD.** `/home/uzver/movian-public-clean` carries staged
changes against `593627edd` (46 files, +763 −10498), including
`support/devtools/mdevlib/{cli,harness,lspdoctor,smoke}.py`. `harness.py` has 1802 lines at
HEAD and 897 in the index. The gap note's `core:…/harness.py` line numbers match the
staged copy, not HEAD. For example, `PORT_RE` is at :38 in the index and at
`mdevlib/harness.py:41` at HEAD. The nav regex the gap note quotes is also the staged one:
`navigator.*Opening (\S+)` in the index, against `navigator.*?Opening (.+)` at
`mdevlib/harness.py:87` [READ]. This note cites HEAD throughout.

**Method.** Each signal was checked in four steps:

1. Find the mdevlib regex or call that depends on it.
2. Look for it on `up:` with `git grep` / `git show`.
3. If it is absent or different there, find the fork commit with
   `git log upstream/master..HEAD -S/-G`. Then place that commit with `git branch -r --contains`:
   either on `up6:`, or on Buksa's side only.
4. Take movian-go's status from the gap note, re-read it in `go:`, and spot-check it in `czz:`.

**Terms.**

- **upstream**: present on `up:`, and therefore also on `up6:`, unchanged.
- **up6-only**: on andoma's `movian6` branch but not on `master`. This is still
  andoma/movian, so it routes as upstream.
- **fork**: only in Buksa's commits (`upstream/movian6..HEAD`).

---

## 0. Answer

The ticket names 12 signals. Four of them cover two behaviours with different origins, so
they are split here into **18 rows**:

- **14 are upstream.**
- **4 are fork-only:**
  - KEYPRESS on HTTP actions;
  - the non-creating `/api/prop` lookup;
  - the GLW convergence-point trace;
  - the raw screenshot API.
- **None is unknown as to origin.** One movian-go status, the STPP binary HELLO in row 15,
  is still **[INFER]**.

**Routing of the 18:**

- **unported → issues in Buksa/movian-go: 8 rows.** They fall into five issues and a
  low-priority tail:
  - the readiness line and the port fallback (rows 1–2);
  - the navigator `Opening` trace (row 3);
  - `/api/input/action` to the UI (row 6);
  - the dev-plugin reload on `ReloadData` with its log lines (rows 4 and 18);
  - the STPP HELLO crash (row 15, settle first);
  - low priority: `/api/ws/echo` (row 16).
- **fork feature → PR proposals to czz: 3 rows.** These are KEYPRESS (row 7), the
  non-creating prop lookup (row 8) and the GLW convergence trace (row 10).
- **No action: 7 rows.** One of them, the raw screenshot (row 13), is a fork feature that
  czz has already taken: `czz:7b9f4a4` "screenshot: request-correlation fixes + raw endpoint
  (from Buksa/movian-go dev)". It is the precedent for the PR route.

The gap note names **15 further signals** that mdev relies on (§3):

- 13 are upstream;
- 1 is up6-only: the dev-plugin FQID `<id>@dev`;
- 1 is fork-only: the gdb ptrace opt-in.

Three of the upstream ones are unported but low priority. Four more dependencies are names,
not core behaviour, and stay on the SDK side (§4).

**Which C movian-go tracks** (gap open question 9) [READ]:

- movian-go follows andoma's `movian6` lineage, not `master`. Its plugin FQID
  `fmt.Sprintf("%s@%s", id, origin)` (go:internal/plugins/plugin_manager.go:459) and its
  `plugins_load_all`/`plguin_repo_load` ports (go:internal/plugins/plugin_init.go:14-16,59)
  have no counterpart on `up:`.
- Its `main.c` line cites match `up6:` and not `up:` or `fork:` HEAD:
  - `parse_opts (src/main.c:523-717)` and `--bypass-ecmascript-acl … (main.c:660)` are at
    go:cmd/movian-go/parseopts.go:3,215;
  - on `up6:` they are at `up6:src/main.c:523,660-661`;
  - on `up:` `parse_opts` starts at 491 and the flag is at 628; on `fork:` they are at 547
    and 708-709.
- The C fork tooling that mdev depends on is absent from movian-go. The one exception is the
  raw screenshot API, which reached czz by PR.

[INFER] movian-go was ported from `up6:`, or from a fork state older than `667475064`
(2026-05-20), which shifted `main.c` lines. Settle it by asking czz.

## 1. Routing table

"present" and "absent" refer to `up:`. Where the fork's commit has a parent of its own,
the fork column lists every commit a port must carry.

| # | signal | mdev depends via | upstream (`up:`) | fork commit | movian-go | route |
|---|---|---|---|---|---|---|
| 1 | readiness line `http-server: Listening on port N` | `mdevlib/harness.py:41` `PORT_RE`, scan `:1146-1164`; `movian_agent.py:80` | **present** `src/networking/asyncio_posix.c:882`, reached from `src/networking/http_server.c:1166-1167` | none | absent (gap R3) | unported → issue |
| 2 | HTTP port falls back off 42000 when taken | port taken from row 1's line (`harness.py:1160-1162`); "isolated profile + dynamic port" (`cli.py:72-76`) | **present** `asyncio_posix.c:822-835` (`bind_any` → port 0); `http_server.c:1166-1167` passes `bind_any=1` | none | different: fixed 42000, no fallback (R4) | unported → issue (with 1) |
| 3 | navigator `Opening <url>` trace | `harness.py:87` `NAV_OPENING_RE`, `:1416-1440`; `smoke.py:530-539`; `movian_agent.py:82` | **present** `src/navigator.c:763` | none | absent (H2) | unported → issue |
| 4 | dev-plugin reload lines `Reloaded dev plugin <p>` / `Unable to reload development plugin: <p>` | `harness.py:54-55`, `:1597-1628`, `:1674-1752` | **present** `src/plugins.c:1278,1280` | none for the wording | absent; Go's unreached line reads `Reloaded dev plugin: %s` (H12) | unported → issue (with 18) |
| 5 | compile error `Unable to compile <p> -- <msg>` | `harness.py:63`, `:1601-1608` | **present** `src/ecmascript/ecmascript.c:841` | none | same (H13) | no action |
| 6 | `/api/input/action/<A>` → `event_to_ui`, so ReloadUI and arrows reach GLW | `harness.py:1642` (ReloadUI); `cli.py:536` (preview flush); `smoke.py:461,474` | **present** `src/api/httpcontrol.c:230` | none; the fork only adds row 7's flag | different: `Dispatch`, not `EventToUI` (H7) | unported → issue |
| 7 | `EVENT_KEYPRESS` on HTTP navigation actions | `smokes/keyboard-mode.json:11,21` through `smoke.py:474` | **absent**: `hc_action` sets no flag (`httpcontrol.c:224-232`); the GLW consumer is upstream (`src/ui/glw/glw.c:2475-2476`) | `024bb4010`, `75295cd20` (#114) | absent (H8) | fork feature → PR to czz |
| 8 | non-creating `/api/prop` lookup: missing path → 404, no side effect | `harness.py:1262-1289` (404 → `None`); `pending_popups` `:1303` | **absent**: GET creates (`src/prop/prop_http.c:32` → `src/prop/prop_core.c:2730`) | `c7fb5aa93`, `1923c5f1b`, tests `35a35390a`; merged `f2c88eb08` (#152, PR #153) | creates, as on `up:` (H5) | fork feature → PR to czz |
| 9 | GLW `Error <f>:<l>: <msg>` from `glw_view_seterr` (parser and preproc errors) | `harness.py:45` `VIEW_ERROR_RE`, `:1635-1656` | **present** `src/ui/glw/glw_view_support.c:500` | none | same (go:internal/ui/glw/glw_view_support.go:95) | no action |
| 10 | GLW convergence-point trace: file-open, lexer, `#include`/`#import` failures | the same regex; without the trace these load failures pass the check (`harness.py:1656`) | **absent**: `src/ui/glw/glw_view.c:241-247,275-280` store `gcv_error` and trace nothing | `617874169` (#92), `8b963ca64` | absent, as on `up:` (H11) | fork feature → PR to czz |
| 11 | `--bypass-ecmascript-acl` | `harness.py:1221-1222`; `cli.py:122-123,736` | **present** `src/main.c:628-630`; `src/ecmascript/es_fs.c:87` | help text only, `667475064`; the ACL it bypasses was widened in `1c3b6161e` | same (P4) | no action |
| 12 | `/api/screenshot`: capture → Imgur → 302, 502 on overlap | not called: `movian_agent.py:73` lists it as blocked ("external-write") | **present** `src/api/screenshot.c:44-56,298` | reworked by `b3df4d747`, `c78336cf8` | same (H9) | no action |
| 13 | `/api/screenshot/raw`, `?raw=1\|true` → PNG; 5 s → 504 | `harness.py:1778`; `smoke.py:420-429`; `movian_agent.py:221-223` | **absent**: only the upload path (`screenshot.c:298`, Imgur `:242`) | `b3df4d747`, `c78336cf8` | same (H9); in czz via `7b9f4a4` | no action (fork feature czz already took) |
| 14 | STPP JSON `[1,sid,0,path]`, `[2,sid]`, `[3,0,path,v]` → notify `[4,…]` | `stpp_probe.py:170-173,202`; `movian_agent.py:318-326,523,539` | **present** `src/api/stpp.c:646-670,1185-1203,1265`; `src/api/stpp.h:23-39` | `277d0a690` (discovery only, not the wire) | same (H17) | no action |
| 15 | STPP binary HELLO `00 03 00` → 19-byte `00 03 <id16> <flags>` | `stpp_probe.py:151-166`; `movian_agent.py:342` | **present** `stpp.c:889-898,1017-1028` | none | **[INFER]** nil-pointer panic (H18) | unported → issue (settle first) |
| 16 | `/api/ws/echo` WebSocket | `movian_agent.py:65,358` | **present** `httpcontrol.c:688-689` | none | absent (H19) | unported → issue (low) |
| 17 | launch flags `-d --disable-upgrades --persistent --cache -p --skin --libav-log --bypass-ecmascript-acl <url>` | `harness.py:1097-1117` | **present** `main.c:546,592,645,642,620,651,550,628,684` | help text, `667475064` | all parsed (R1) | no action |
| 18 | `ReloadData` → `nav_reload_current` → `plugins_reload_dev_plugin` | `harness.py:1701` | **present** `navigator.c:863-874,933-934`; `plugins.c:1264-1282`; GLW forwards to the navigator (`glw.c:1881-1892`) | none | absent: never called, and `devPlugins` is nil (H12) | unported → issue (with 4) |

Tally: 14 upstream (1–6, 9, 11, 12, 14–18), 4 fork-only (7, 8, 10, 13). Routes: 8 unported
(1, 2, 3, 4, 6, 15, 16, 18), 3 PRs (7, 8, 10), 7 no action (5, 9, 11, 12, 13, 14, 17).

**czz master agrees with `go:` on every routed row** [READ, `git grep` on `czz:`]:

- rows 1, 2: there is no `Listening on port` outside `internal/asyncio/{tcp,udp}.go`, and
  `ctx.httpServer.Listen(42000)` is at `czz:cmd/movian-go/wire_network.go:451`;
- row 3: there is no `"Opening %s"` in `internal/navigator`;
- row 6: `h.eventMgr.Dispatch(e)` is at `czz:internal/api/httpcontrol/httpcontrol.go:104`;
- rows 4, 18: `plugins.Start(…, nil)` is at `czz:cmd/movian-go/wire_network.go:101`, and
  `Reloaded dev plugin: %s` is at `czz:internal/plugins/plugin_init.go:135`;
- row 7: there is no `EventKeypress` under `internal/api`;
- row 8: `pm.CreateEx(p, name, …)` is at `czz:internal/prop/prop_registry.go:234`;
- row 10: the only GLW `Error %s:%d` is `czz:internal/ui/glw/glw_view_support.go:95`;
- row 15: `MgppHandleBinary(apiMgpp, nil, …)` is at `czz:cmd/movian-go/wire_network.go:423`;
- row 16: there is no `ws/echo`.

## 2. Per signal

### Rows 1–2. The readiness line and the port fallback

- **mdev.** `launch()` starts the core and scans its log for 30 s for
  `PORT_RE = r"http-server: Listening on port (\d+)"`. It records the matched port in
  `state.json` and kills the child if the line never comes (`mdevlib/harness.py:41,1120-1189`)
  [READ]. `mdev run` lets instances coexist because the port is whatever that line says
  (`mdevlib/cli.py:72-76`) [READ].
- **upstream** [READ]:
  - `http_server_init` calls `asyncio_listen("http-server", 42000, http_accept, NULL, 1)`
    (`up:src/networking/http_server.c:1166-1167`).
  - `asyncio_listen` traces `"%s: Listening on port %d"` with the *bound* port
    (`up:src/networking/asyncio_posix.c:870-882`).
  - With `bind_any=1`, a failed bind on 42000 sets `port = 0` and binds an ephemeral port
    (`up:…/asyncio_posix.c:803,822-835`).
  - The emitted line is `TCP [INFO]: http-server: Listening on port N`. The regex is
    unanchored and ignores the subsystem.
- **fork.** No commit in `upstream/master..HEAD` touches `asyncio_posix.c` or
  `http_server_init` [READ: `git log`; `git diff upstream/master HEAD -- src/networking/asyncio_posix.c`
  is empty].
- **movian-go** [READ]:
  - `HTTPServer.Listen` is a bare `net.Listen("tcp", ":42000")` that logs nothing on success
    (go:internal/networking/http/http_server.go:395-409).
  - Failure traces `Failed to start HTTP control server` (go:cmd/movian-go/wire_network.go:451,461-463).
  - Go's `asyncio` layer has the identical trace (go:internal/asyncio/tcp.go:146-147), but
    HTTP does not use it (gap R3, R4).
- **route.** unported → one issue in Buksa/movian-go: "HTTP server listens through asyncio
  with `bind_any`". The STPP announcer's hard-coded 42000
  (go:cmd/movian-go/wire_network.go:495) has to follow the bound port too [READ].

### Row 3. The navigator `Opening <url>` trace

- **mdev** [READ]:
  - `open_and_wait` does not trust the prop tree until the log delta shows
    `NAV_OPENING_RE = r"navigator.*?Opening (.+)"` equal to the requested URL. It re-issues
    the GET up to four times (`mdevlib/harness.py:87,113-114,1416-1440`).
  - The health smoke needs the same trace (`mdevlib/smoke.py:530-539`).
  - The agent counts it as `navigation` (`mdevlib/movian_agent.py:82`).
- **upstream.** `nav_open0` begins with `TRACE(TRACE_INFO, "navigator", "Opening %s", url)`
  (`up:src/navigator.c:763`), identically on `fork:` [READ].
- **fork.** none. The fork changed only mdev's regex, from `(\S+)` to `(.+)` for URLs with
  spaces (`mdevlib/harness.py:79-86`) [READ].
- **movian-go.** `navOpen0` has no trace (go:internal/navigator/navigator_open.go:315-346;
  gap H2) [READ].
- **route.** unported → issue. This is one line, and it unblocks `open`, `preview`, the
  `health` and `open-home` smokes (gap S2).

### Rows 4 and 18. `ReloadData` and the dev-plugin reload lines

- **mdev** [READ]:
  - `do_reload_js` POSTs `/api/input/action/ReloadData` and waits for one result per
    recorded `-p` dir (`mdevlib/harness.py:1674-1752`).
  - Success is `RELOAD_JS_OK_RE = r"Reloaded dev plugin (\S+)"`. Failure is
    `RELOAD_JS_FAIL_RE = r"Unable to reload development plugin: (\S+)"`, or the compile
    line of row 5 (`:54-55,63`).
  - Paths are compared after `file://` normalisation (`:1611-1628`).
- **upstream** [READ]. The whole path exists on `up:`:
  - `"ReloadData"` maps to `ACTION_RELOAD_DATA` (`up:src/event.c:195`);
  - GLW forwards that action to the navigator's `eventSink` (`up:src/ui/glw/glw.c:1881-1892,2549-2566`);
  - the navigator calls `nav_reload_current` (`up:src/navigator.c:933-934`);
  - `nav_reload_current` calls `plugins_reload_dev_plugin()` under `ENABLE_PLUGINS` (`:863-874`);
  - that function reloads every `-p` path and traces
    `"Unable to reload development plugin: %s\n%s"` or `"Reloaded dev plugin %s"`
    (`up:src/plugins.c:1264-1282`);
  - `-p` paths are stored after `fa_normalize`, so the success line names a `file://` URL
    (`up:src/plugins.c:1240-1245`).
- **fork** [READ]:
  - The wording and the flow are unchanged.
  - The only difference is the extra origin argument `"dev"` to `plugin_load`
    (`fork:src/plugins.c:1435,1465`). It comes from `up6:` (`666f814b3`), not from Buksa.
- **movian-go** [READ]:
  - `navReloadCurrent` reloads the page only (go:internal/navigator/navigator_page.go:657-669).
  - `plugins.ReloadDevPlugin` has no caller, and it iterates `pm.devPlugins`, which is nil:
    `plugins.Start(…, nil)` (go:cmd/movian-go/wire_network.go:101;
    go:internal/plugins/plugin_init.go:17-23,116-138).
  - Its lines would not match anyway: `Reloaded dev plugin: %s` has a colon, and the failure
    reads `Failed to reload dev plugin` (:133,135) (gap H12).
- **route.** unported → one issue covering three changes: call the dev-plugin reload from
  `navReloadCurrent`, pass the `-p` paths to `plugins.Start`, and use the C wording.

### Row 5. `Unable to compile <path> -- <msg>`

- upstream `up:src/ecmascript/ecmascript.c:841`;
- unchanged on `fork:`;
- the same in go:internal/ecmascript/ecmascript.go:1022 (gap H13) [READ].

No action.

### Rows 6–7. `/api/input/action`: routing to the UI, and the KEYPRESS flag

These are two behaviours, with different origins.

- **mdev** [READ]:
  - `mdev reload` POSTs `ReloadUI` and greps for GLW errors (`mdevlib/harness.py:1635-1656`).
  - `mdev preview` POSTs `ReloadUI` to flush the view cache (`mdevlib/cli.py:536`).
  - The smokes POST `ReloadUI` and named actions (`mdevlib/smoke.py:461,474`).
  - The `keyboard-mode` smoke posts `down` twice and expects `global/userinterfaces/ui/keyboard`
    to become 1 (`fork:support/devtools/smokes/keyboard-mode.json:11,21`).
- **Row 6, routing: upstream** [READ]:
  - `hc_action` is `event_to_ui(event_create_action_str(remain))` (`up:src/api/httpcontrol.c:224-232`).
  - `event_to_ui` sends to `global.userinterfaces.ui.eventSink`, i.e. GLW (`up:src/event.c:541-547`).
  - GLW handles `ReloadUI` by `glw_load_universe` (`up:src/ui/glw/glw.c:2497-2499`).
- **Row 7, the flag: fork-only** [READ]:
  - `up:` `hc_action` sets no `e_flags`. Every other remote path does: lirc, devevent, stdin
    and libcec (`up:src/ipc/lirc.c:126`; `up:src/ipc/stdin.c:160`).
  - GLW switches to keyboard mode only for `EVENT_KEYPRESS` (`up:src/ui/glw/glw.c:2475-2476`).
  - The fork's `hc_action` sets the flag for up/down/left/right/activate/back/focus/page/top/bottom,
    and nothing else, so a screensaver wake does not swallow `ReloadUI`
    (`fork:src/api/httpcontrol.c:227-261`).
  - It came in two commits:
    - `024bb4010 httpcontrol: mark /api/input/action events as keypresses (#114)` (2026-07-17);
    - `75295cd20 httpcontrol: limit EVENT_KEYPRESS to navigation actions (#114)` (2026-07-18).
- **movian-go** [READ]:
  - The handler calls `h.eventMgr.Dispatch(h.eventMgr.CreateActionStr(remain))`
    (go:internal/api/httpcontrol/httpcontrol.go:94-107).
  - `Dispatch` ports `event_dispatch`, not `event_to_ui` (go:internal/event/event.go:983).
  - `EventToUI` exists (:1130) but is not called here (gap H7, H8).
  - **[INFER]** (gap H7): `ReloadUI` and arrow keys never reach GLW, while `ReloadData` still
    reaches the navigator.
- **route:**
  - row 6: unported → issue ("`/api/input/action` uses `EventToUI`, as C does");
  - row 7: fork feature → PR to czz.
  - **Order matters** [INFER]. The KEYPRESS flag is read only by GLW, and GLW sees only
    `ui.eventSink`, so the PR for row 7 does nothing until row 6's issue is fixed.

### Row 8. The non-creating `/api/prop` lookup

- **mdev** [READ]:
  - `get_prop` returns `None` on a 404, and that is how `mdev props` says "not found"
    (`mdevlib/harness.py:1262-1289`).
  - `pending_popups` needs the 404/200 difference (`:1303`).
- **upstream** [READ]:
  - `prop_from_path` is `prop_get_by_name(strvec_split(path,'/'), 1, NULL)`
    (`up:src/prop/prop_http.c:28-35`).
  - That walks `prop_subfind`, which **creates** every missing child:
    `p = c ?: prop_create0(p, name[0], NULL, 0)` (`up:src/prop/prop_core.c:2682,2730`).
  - So on upstream a GET of a missing path under `global` answers 200 `(void)` and leaves
    the prop behind.
  - The non-creating `prop_findv` exists on `up:` but has no indexing parameter
    (`up:src/prop/prop_core.c:5049`).
- **fork** [READ]:
  - `prop_from_path` is `prop_findv(prop_get_global(), n + 1, 1)` and only accepts `global`
    roots (`fork:src/prop/prop_http.c:29-35`).
  - Commits:
    - `c7fb5aa93 prop: make HTTP lookup non-creating` (2026-07-22);
    - `1923c5f1b prop: add allow_indexing parameter to prop_findv for HTTP positional lookup`
      (2026-07-28), which restores `*N` indexing that `c7fb5aa93` alone had broken;
    - `35a35390a tests: cover indexed non-creating prop lookup`;
    - merged as `f2c88eb08` "Merge pull request #153 from Buksa/Buksa/issue-152-prop-http-index".
- **movian-go.** `propFromPath` ports the upstream `prop_get_by_name` line for line
  (go:internal/prop/http/prop_http.go:30-37). Its `Subfind` creates
  (go:internal/prop/prop_registry.go:233-236; gap H5) [READ].
- **route.** fork feature → PR to czz. A port must carry both `c7fb5aa93` and `1923c5f1b`
  [READ: the commit subjects].

### Rows 9–10. GLW view-load error traces

- **mdev** [READ]:
  - `VIEW_ERROR_RE = r"GLW\s+\[ERROR\]:\s*Error (.+?):(\d+): (.*)$"` (`mdevlib/harness.py:45`).
  - `do_reload` reports `ok` when no such line appears within the settle window (`:1635-1656`).
- **Row 9: upstream** [READ]. `glw_view_seterr` traces `"Error %s:%d: %s"`
  (`up:src/ui/glw/glw_view_support.c:500`). That covers errors raised through `seterr`:
  parser, preproc and eval.
- **Row 10: fork-only** [READ]:
  - On `up:`, a view file that fails to open sets `gcv_error` and returns
    (`up:src/ui/glw/glw_view.c:241-247`).
  - The `bad:` label records the lexer's or `#include`'s `errorinfo_t`, also without a trace
    (`:275-280`).
  - The fork traces both: the file-open failure (`fork:src/ui/glw/glw_view.c:246`), and the
    convergence point when the error did not already pass through `seterr` (`:282-288`).
  - Commits:
    - `617874169 glw: TRACE_ERROR all view-load failure classes, not just parser errors (#92)`
      (2026-07-12);
    - `8b963ca64 devtools+glw: pipeline-end review fixes — … zero-init errorinfo_t in eval_loaded_view`
      (2026-07-13), which makes the new `traced` field reliable.
- **movian-go** [READ]:
  - It traces in `glwViewSeterr` (go:internal/ui/glw/glw_view_support.go:95).
  - Its open and lexer failure paths are a faithful port of upstream's silent ones
    (go:internal/ui/glw/glw_view.go:373-381,401-407; gap H11).
- **route:**
  - row 9: no action;
  - row 10: fork feature → PR to czz, carrying both commits.
  - [INFER] Without row 10, a missing view file or a lexer error passes `mdev reload` and
    `mdev preview` with no error on movian-go. Upstream C behaves the same way.

### Row 11. `--bypass-ecmascript-acl`

- **mdev.** `ensure_running` passes the flag for `mdev preview`, and `mdev run
  --bypass-ecmascript-acl` passes it on request (`mdevlib/harness.py:1201-1222`;
  `mdevlib/cli.py:122-123,736`) [READ].
- **upstream** [READ]:
  - parsed at `up:src/main.c:628-630`;
  - it short-circuits `get_filename`'s ACL (`up:src/ecmascript/es_fs.c:87`);
  - it is missing from upstream's `--help` text.
- **fork** [READ]:
  - `667475064 Align CLI help with option parser` (2026-05-20) adds the flag to the help text;
  - `1c3b6161e ecmascript: enforce file handle read ACL` (2026-06-21) puts more reads under
    the ACL that the flag bypasses. Its semantics are unchanged.
- **movian-go.** Parsed (go:cmd/movian-go/parseopts.go:216) and read in
  go:internal/ecmascript/es_fs.go:54 (gap P4) [READ].
- **route.** No action.

### Rows 12–13. `/api/screenshot` and its raw form

- **mdev** [READ]:
  - `take_shot` GETs `/api/screenshot/raw` and checks image magic
    (`mdevlib/harness.py:1765-1801`).
  - The health smoke requires a PNG (`mdevlib/smoke.py:420-429`).
  - The agent tests `/raw` and `?raw=1` (`mdevlib/movian_agent.py:221-223`), and lists plain
    `/api/screenshot` under `BLOCKED_HTTP_PROBES` as "external-write" (`:69-74`).
- **upstream** [READ]:
  - `/api/screenshot` only (`up:src/api/screenshot.c:298`).
  - It answers 502 if a capture is already pending (`:44-56`).
  - It encodes, uploads to Imgur and redirects (`:242-268`).
  - There is no raw path, no query alias and no timeout.
- **fork** [READ]:
  - `b3df4d747 Add raw screenshot API` (2026-05-17);
  - `c78336cf8 Correlate screenshot requests with events` (2026-05-17).
  - Together they add `hc_screenshot_raw` with a 5 s wait → 504, and the `/raw`,
    `?raw=1` and `?raw=true` selectors (`fork:src/api/screenshot.c:71-113,142-150,453`).
- **movian-go** [READ]:
  - Same contract (go:internal/api/screenshot/screenshot.go:65-79; gap H9).
  - It is on czz `master` as `7b9f4a4 screenshot: request-correlation fixes + raw endpoint
    (from Buksa/movian-go dev)` (2026-10-09). The local `go:` has its own `10775f3`.
  - Gap H10 ("early capture → 504, not replayed") is a readiness difference. It is not part
    of the raw contract.
- **route.** No action for either row. Row 13 is the worked example of the fork-feature
  route.

### Rows 14–16. STPP and the echo WebSocket

- **mdev** [READ]:
  - `stpp_probe` opens `/api/stpp` (`mdevlib/stpp_probe.py:72`).
  - It sends JSON set `[3,0,path,v]`, subscribe `[1,sid,0,path]` and unsubscribe `[2,sid]`,
    and waits for notify `[4,sid,…]` (`:170-202`).
  - With `--binary-hello` it sends `00 03 00` and requires a 19-byte binary reply starting
    `00 03` (`:151-166`).
  - `movian_agent` does the same (`mdevlib/movian_agent.py:318-326,342`) and opens
    `/api/ws/echo` (`:358`).
- **upstream** [READ]:
  - wire constants, "no changes here please" (`up:src/api/stpp.h:23-39`);
  - the JSON dispatcher (`up:src/api/stpp.c:646-670`) and the frame demux (`:1185-1203`);
  - the HELLO reply `[HELLO, 3, running_instance[16], flags]` (`:889-898`), sent on any
    binary HELLO (`:1017-1028`);
  - `/api/stpp` registration (`:1265`);
  - `/api/ws/echo` registration (`up:src/api/httpcontrol.c:688-689`).
- **fork.** Only `277d0a690 Zero STPP discovery messages before fill`. That is discovery,
  not the WebSocket protocol: `git diff upstream/master HEAD -- src/api/stpp.c` is 7 lines
  [READ].
- **movian-go** [READ]:
  - JSON is ported with the same constants (gap H17).
  - Binary frames are dispatched with a nil client: `MgppHandleBinary(apiMgpp, nil, …)`
    (go:cmd/movian-go/wire_network.go:423).
  - `MgppSendHello` reads `client.instanceID` (go:internal/api/mgpp/mgpp_cmd.go:263-275).
  - **[INFER]** HELLO panics on a nil pointer (gap H18). To settle: send `00 03 00` to a
    throwaway movian-go.
  - `/api/ws/echo` is absent (gap H19).
- **route:**
  - row 14: no action;
  - row 15: unported → issue, once settled;
  - row 16: unported → issue, low priority, because only the agent's self-test uses it.

### Row 17. Launch flags

`build_argv` emits `stdbuf -oL -eL ./build.debug/movian -d --disable-upgrades --persistent <dir>
--cache <dir> [-p <abs>]… [--skin <abs>] [--libav-log] [--bypass-ecmascript-acl] [<url>]`
(`mdevlib/harness.py:1097-1117`) [READ].

| flag | `up:src/main.c` | fork | movian-go (go:cmd/movian-go/parseopts.go) |
|---|---|---|---|
| `-d` (trace level DEBUG) | :546-549 | — | :103 |
| `--disable-upgrades` | :592-595 | help text `667475064` | :154 |
| `--persistent <p>` | :645-647 | alias `-s` added (not used by mdev) | :241 |
| `--cache <p>` | :642-644 | — | :236 |
| `-p <dir>` | :620-623 | — | :204 |
| `--skin <dir>` | :651-653 | — | :199 |
| `--libav-log` | :550-553 | — | :108 |
| `--bypass-ecmascript-acl` | :628-630 | help text `667475064` | :216 |
| positional start URL | :684 | — | :307 |

Things mdev does **not** pass to the core [READ]:

- `--plugin` is mdev's own argparse alias (`mdevlib/cli.py:688`). `plugin_dirs_from_argv`
  tolerates it when reading a stored argv (`mdevlib/harness.py:1666`), but neither core
  parses it.
- `--ui` is never passed. It is upstream (`up:src/main.c:648`) and was removed in Go
  (gap R1).
- `--debug-glw` is never passed. It gates every `GLW_TRACE` (`up:src/ui/glw/glw.h:41-44`).
- The only trace flag passed is `-d`.

Also part of the launch:

- `stdbuf` line-buffers libc stdio and is not a core flag. [INFER] It does nothing to a Go
  binary, and the harm is nil.
- The environment variable `MOVIAN_MDEV_ALLOW_GDB=1` is fork-only (E13 below).

Route: no action.

## 3. Further signals the gap note names

| # | signal | mdev depends via | upstream (`up:`) | fork commit | movian-go | route |
|---|---|---|---|---|---|---|
| E1 | trace prefix `%-15s [%-5s]:`, which gives the `GLW [ERROR]:` and `navigator … Opening` shapes | `harness.py:45,87` | **present** `src/trace.c:168` | none | same, plus Go `log` date stamp (R9) | no action |
| E2 | page props `global/navigators/current/currentpage/{url,model/loading,…}` | `harness.py:97-101,115` | **present** `src/navigator.c:251-255` | none | same names (H3) | no action |
| E3 | `global/userinterfaces/ui/{framerate,keyboard}` | `smoke.py:27,532`; `keyboard-mode.json` | **present** `src/ui/glw/glw.c:690,3461` | none | same (H14) | no action |
| E4 | `Loaded dev plugin <p>` (agent `plugin_ready`) | `movian_agent.py:81` | **present** `src/plugins.c:1252` | none | same line; path not normalised (P1) | no action |
| E5 | `Route <p> added` (agent `plugin_ready`) | `movian_agent.py:81` | **present** `src/ecmascript/es_route.c:143` (debug) | none | same (go:internal/ecmascript/es_route.go:109) | no action |
| E6 | `/api/open?url=` → open + 302 | `harness.py:1398-1404` | **present** `src/api/httpcontrol.c:50-65` (`event_to_ui`) | none | same shape through `navSys.Open` (H1) | no action |
| E7 | `/api/diag` `<strong>movian</strong> Version X` | `movian_agent.py:393`; `movian_diag_snapshot.py:176` | **present** `httpcontrol.c:349` | none | hard-coded `9.0.0` (H15) | unported → issue (low) |
| E8 | `/api/ecmascript/stats`, `/gc` | `movian_agent.py:379,440`; `movian_diag_snapshot.py:185-197` | **present** `src/ecmascript/es_stats.c:153-154` | none | same text; memory ≠ JS heap (H16) | no action (engine difference) |
| E9 | `/api/logfile/<n>` serves the file the trace writes | `movian_agent.py:62,204` | **present**: both use `gconf.cache_path` (`httpcontrol.c:377`; `src/trace.c:325`) | none | **[INFER]** a different directory under a split `--cache` (H21) | unported → issue (low) |
| E10 | `global/stpp/remoteControlled` | `movian_agent.py:38,309-332` | **present** `src/api/stpp.c:1222-1225` | none | same (H20) | no action |
| E11 | dev-plugin FQID `<id>@dev`, giving storage `<persistent>/plugins/<id>@dev` and service `plugin:<id>@dev` | `harness.py:361,495-506` (`--plugin-setting`); `:1273-1277` | **absent on master**: storage is `<persistent>/plugins/<id>` (`src/ecmascript/ecmascript.c:881-882` ← `src/plugins.c:667`); **present on `up6:`** `src/plugins.c:240,726,1435,1465` | `666f814b3`, `4c87b2b0f` (Andreas Smas, 2018-12, on `up6:`) | same as `up6:` (go:internal/plugins/plugin_manager.go:459; plugin_ecmascript.go:86) | no action |
| E12 | `--dev-flags` → store `("dev", id)` | `cli.py:88-94` | **present** `src/settings.c:1496` | none | same key (R8); runtime unverified | no action |
| E13 | `MOVIAN_MDEV_ALLOW_GDB=1` → `PR_SET_PTRACER_ANY` | `harness.py:35,1133`; `smoke.py:903` | **absent** | `3e94891cf mdev: capture owned process stacks on smoke wedges` | absent (R7) | fork feature; no PR proposed, because the map captures Go wedges with `SIGQUIT` |
| E14 | GLW focus and event-route traces (agent `glw_focus`) | `movian_agent.py:83` | **present** `glw.c:1445,1473,1913`, only with `--debug-glw` | none | route-start ported (go:internal/ui/glw/events.go:156); focus traces are comments only (go:internal/ui/glw/focus.go:268,287) | unported, but advisory and never enabled by mdev; no issue needed |
| E15 | keyboard mode switches on a KEYPRESS event | through row 7 | **present** `glw.c:2475-2476` | none | present (go:internal/ui/glw/events.go:588-603) | no action; row 7 is the producer |

All cites in the `upstream` column are `up:` [READ]. E9 is [INFER] only for the runtime
directory. The handler's root is `filepath.Join(persistentPath, "cache")`
(go:cmd/movian-go/wire_network.go:347), while the trace writes under `gconf.CachePath`
(go:cmd/movian-go/wire_core.go:146) [READ].

## 4. Dependencies that are names, not core behaviour

These depend on what a binary or window is called, or on a plugin the SDK ships. They are
upstream by origin, but the route is **SDK-side** for all of them: mdev adapts through the
core-kind seam, and movian-go is not asked to rename anything.

- **Process identity** `comm == "movian"`, or argv basename `movian` (`mdevlib/harness.py:232-252,314-319`).
  Upstream names the program `movian` (`up:Makefile:36`); movian-go's is `movian-go` (gap R5).
- **Binary path** `./build.debug/movian` and smoke `needs.binary` (`mdevlib/harness.py:34`;
  `mdevlib/smoke.py:345-348`). The layout `build.${BUILD}/movian` is upstream
  (`up:Makefile:25,36`). The `support/configure-linux-debug.sh` wrapper is fork-only
  (`275c334a1`). movian-go builds `./movian-go` (gap L3, S1).
- **X11 window name** `Movian` (`mdevlib/x11_keypress.py:35`; `x11_pointer.py:71`). It is
  `APPNAMEUSER` (`up:support/configure.inc:353`; `up:src/ui/glw/glw_x11.c:314`). movian-go
  calls it `Movian Go` (gap X1).
- **`viewpreview: ERROR:`** (`mdevlib/harness.py:50`) is printed by the SDK-side plugin's
  own `console.log` (`fork:support/devtools/viewpreview/viewpreview.js:30-35`), not by a
  core. Its host contract is upstream: the `raw` page type with `metadata.glwview`
  (`up:glwskins/flat/pages/raw.view:5`).

## 5. What this means for the spec

**Three of mdev's proofs are fork contracts, not Movian contracts.** These are KEYPRESS
(row 7), 404 on a missing prop (row 8) and the convergence trace (row 10). [INFER] The
same failures would show on an andoma-master C build:

- the `keyboard-mode` smoke would fail;
- `mdev props` would print `(void)` for a typo;
- a missing view file would pass `mdev reload` with no error.

So these PRs are not about Go parity alone. They write down behaviour that only this
fork's C has, and the spec should name them as part of the core contract mdev requires.

**Everything else mdev waits for is plain upstream Movian.** The eight unported rows are
upstream behaviour that the Go port left out or changed. That is the issue route, and each
issue can cite `up:` line numbers that czz's own comments already use.

## Open questions

1. **Does "upstream" for routing include andoma's `movian6` branch (`up6:`)?** It is
   andoma/movian, and it is the lineage movian-go was ported from (§0). Recommendation: yes.
   Only E11 depends on the answer, and it routes to no action either way.
2. **How do the eight unported rows become issues?** Recommendation: five issues, plus the
   low tail folded into one:
   - (i) rows 1+2: listen through asyncio with `bind_any`;
   - (ii) row 3;
   - (iii) row 6;
   - (iv) rows 4+18;
   - (v) row 15, after settling it;
   - tail: row 16, E7, E9.
   This belongs to the map's "Packaging the movian-go gaps".
3. **Must the row-6 issue land before the row-7 PR?** [INFER] Yes, because the flag does
   nothing until HTTP actions reach `ui.eventSink`. Should the PR be held, or sent with a
   note?
4. **Does a port of row 8 or row 10 carry the fork's follow-up commits?** The fork needed
   a second commit for each: `1923c5f1b` restored `*N` indexing, and `8b963ca64` zero-inits
   `errorinfo_t`. A PR that takes only the first commit reintroduces the bug that the second
   one fixed.
5. **Row 15 is still [INFER].** Does a binary HELLO crash movian-go? It is settled by one
   `stpp_probe --binary-hello` against a throwaway instance, which this survey did not
   launch.
6. **Whose state does the gap inventory describe?**
   - Its `core:…/mdevlib` line cites match the fork checkout's *staged index*, not
     `593627edd`.
   - Its `go:` refers to a local WIP branch (`10775f3`) that is on no remote.
   - The routed rows agree with `czz:` `d761987` and with fork HEAD.
   - Should tickets cite HEAD and `czz:` from now on, and should the gap note say which
     state it read?
7. **Is the PR path Buksa/movian-go `dev` → czz, as `7b9f4a4` was?** czz took the raw
   screenshot "from Buksa/movian-go dev". Should the three fork-feature PRs (rows 7, 8, 10)
   go the same way?
