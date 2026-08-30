---
name: verify
description: Judge whether a Movian plugin change actually works — what counts as proof, what counts as noise, and how much verification a change needs. Use when asked to smoke-test a plugin change, verify a route/prop/screenshot really changed, decide whether a fix is proven, diagnose a false pass or a false failure, or choose the minimum evidence for a change. Mechanics of launching and driving Movian live in the run skill.
---

# Verifying a Movian plugin change

> **Resolving `mdev` first.** Every `mdev` command below assumes the shim is
> reachable. It often is not: an agent session runs a **non-login,
> non-interactive** shell, which reads neither `~/.profile` nor `~/.bashrc`, so
> `mdev` is on `PATH` only if whatever launched the session happened to put it
> there. (A login shell — `bash -lc` — *is* non-interactive but does read
> `~/.profile`; the shape without any startup file is the plain `bash -c` an
> agent gets.) Do not rely on inheritance.
>
> Once per session, before the first `mdev` command, resolve it and use the
> resolved path for the rest of the session:
>
> ```sh
> command -v mdev \
>   || { p="$(jq -er '.bin // empty' "${MOVIAN_SDK_CONFIG:-$HOME/.config/movian-sdk/config.json}")/mdev" \
>        && [ -x "$p" ] && printf '%s\n' "$p"; } \
>   || { p="${MOVIAN_SDK_BINDIR:-$HOME/.local/bin}/mdev"; [ -x "$p" ] && printf '%s\n' "$p"; }
> ```
>
> Three steps, each earning its place. `jq -er` with `// empty` because a config
> written before the `bin` key existed would otherwise make `.bin + "/mdev"`
> print **`/mdev`** — a nonexistent path, with exit 0. `[ -x ]` because a
> recorded path that no longer exists must not be handed back as an answer. And
> the last step because `./install.sh` **without** a core path installs the shims
> and writes no config at all, so a config-only lookup would report "not
> installed" on a machine where `mdev` is sitting in `~/.local/bin`.
>
> If none of the three answers, the SDK really is absent here — say so rather
> than guessing a path, and point at the installer:
> `cd movian-plugin-sdk && ./install.sh /abs/path/to/movian/checkout`.
> This preamble is repeated in every `movian:*` skill on purpose, because skills
> load individually and you may be holding only this one. `tests/reachable_selftest.py`
> asserts that all seven copies stay identical.


This skill is about **judgment**, not mechanics. Use `movian:run` for the
commands; use this for deciding whether what came back means anything.

## Before touching anything: state falsifiable criteria

Write down the narrow thing that would prove *or disprove* the change before
launching: target route or user flow, expected page title/type/loading state,
expected metadata fields, expected node count or key row types, expected visual
state, disallowed log patterns.

Use the smallest flow that can prove the change. A broad "smoke everything" pass
is not a substitute for one targeted assertion.

## Transport success is not proof

HTTP 200 and an `eventSink` `OK` prove only that the request was *accepted*.
They never prove the intended effect happened. Verify the actual mutation: the
prop value changed, the route transitioned, the popup closed, playback started,
the screenshot shows the expected frame.

## Page-ready has a trap

"Ready" is not simply `loading == 0`. A page counts as ready when `model/loading`
is `"0"` **or absent** — some routes never create a `loading` prop at all (any
`page:*` URL is one; the real settings page is `settings:`) — **and** the title
prop has a real value.

Do not stop at `loading=0`: a redirect or protocol root can leave `loading=0`
while `currentpage.url` still points at the *previous* page. Require the expected
title and type, and for redirects also the expected `currentpage.url`.

## Reading props without corrupting them

- HTTP paths (`/api/prop/...`, `mdev props ...`) are slash-separated and start at
  `global`. Unnamed children display as `*N` — an HTTP display alias, not a real
  path component.
- STPP JSON paths are dot-separated, relative to propref `0`, and **omit** the
  `global.` prefix. Never reuse an HTTP slash path or a `*N` alias in STPP.
- A named path that does not exist yet is **not** a harmless 404: path resolution
  follows symlinks and enables indexing, so a typo can materialise a new void
  prop in the tree. Read the known parent first, copy the child name from the
  response, then descend one segment at a time.
- Read a row's `url` and call `/api/open?url=...` for ordinary navigation.
  Reserve POST `action=Activate`/`action=Ok` to an `eventSink` for action rows,
  popups and option controls — not for rows that have a real URL.
- On a fresh profile, dismiss first-launch popups (plugin TOS and friends) with
  `action=Ok` to `global/popups/*0/eventSink` **before** the first `/api/open`,
  unless the popup is itself under test. An undismissed popup can leave the
  navigator at `page:home` with void model props even after `/api/open` reports
  success.

## Anti-flake timing

- `prop.subscribeValue()` fires once immediately on subscribe. Treat that first
  callback as current state, not as a user action.
- Wait for the concrete prop that proves the flow, never a fixed sleep: title
  plus `loading` for a route, node `url`/title for a row, the popup node before
  sending `Ok`, playinfo props before asserting resume state.
- View-parse errors surface in the log within a couple hundred milliseconds of a
  reload, but a prop-driven view change is dispatched to the GLW thread
  asynchronously and can land slightly *after* the page reports ready. Poll the
  log over a short settle window rather than reading it once.

## Known false green: reload exit codes

`mdev reload` and `mdev preview` only grep the log for GLW **parser/preprocessor**
errors. A `.view` **lexer** error — an unterminated string literal, say — or a
failed file open on the target `.view` matches neither pattern and is invisible
to their exit code. They will report a clean reload while the view did not load.

Never accept a bare `mdev reload`/`preview` exit 0 as proof for a `.view` syntax
change. Read `mdev log --tail` and look for any `GLW` line near the reload, or
take a screenshot.

## Error-signal triage

Grep the log **delta**, not the whole log, for: `TypeError`, `ReferenceError`,
`Cannot read property`, `Unable to load image`, `Unknown format`, a
plugin-specific error trace, or a GLW view-parse error. `mdev log --errors`
already applies this set.

Ignore known noise: repository and update checks against the dead `movian.tv`
produce network errors unrelated to your change, unless repo/update behaviour is
itself under test.

## Hash before vision

`mdev shot` prints `sha256=<hex>` and stores it as `last_shot_hash`.

Before sending a screenshot to a vision model, query the verdict cache with that
hash **and the exact question**. If `(hash, question)` is cached, reuse the
verdict. If not, send the image and cache the answer under that pair — even when
a different question was already judged for the same image.

`mdev shot --if-changed` exits 3 when the bytes match the previous capture. Exit
3 is **not** a verdict-cache hit: on a cache miss, send the retained
`last_shot_path`.

This saves external quota, because GLW static-page rendering is deterministic. A
matching hash proves identity; it never proves non-identity.

## The evidence ladder

Five levels. Each is a different **kind** of claim, not a different amount of
effort.

| | evidence | proves | does not prove |
|---|---|---|---|
| **L0** static | `node --check`, `tsc --noEmit` against `mdev types`, `git diff --check` | the file parses; the modules and members it names exist — *if* `mdev types` reported `typefloor: OK` | that a single line runs |
| **L1** loads | the plugin appears in the log with no load-time error | manifest and entry point are valid | that any route works |
| **L2** route | `mdev open <url>` reaches page-ready | navigation reached your handler and it returned | that the page holds the right thing |
| **L3** state | `mdev props` shows the specific values under test | the change's effect on the model | that any of it is visible |
| **L4** visual | `mdev shot`, inspected | what the user actually sees | why it looks that way |

**A lower level passing never implies a higher one. A higher level passing does
imply the lower ones** — you cannot render a route you failed to load. So verify
at the highest level your change can reach, and say which level you reached.

L0 is the one rung whose *instrument* can be silently empty. A `.d.ts` generated
by a core checkout older than the declarations produces a clean `tsc` on code
that names members which do not exist (movian#183). `mdev types` and `mdev
doctor` now compile a deliberately-wrong probe against it and print
`typefloor: OK` or `FAILED`. A green `tsc` reported without that line is an
unverified claim, not L0.

Playback is not a sixth rung; it is a **sub-ladder inside L3–L4** —
`routed` → `probed` → `decoded` → `rendered`, each proving only its own layer
(`references/media-playback-smoke.md`).

## The gate underneath the ladder

Before trusting evidence at any level, prove the instance is alive:

```
mdev smoke run health --name <the instance you just launched>
```

Pass the **same `--name` you launched**, or you are probing a different process
than the one you are about to trust. Exit 2 means `mdev stop` and relaunch, not
retry.

A wedged GLW instance keeps answering HTTP while dispatching nothing, so it
manufactures a plausible failure at every level at once — an open that returns
200 and never navigates, a screenshot that times out, props frozen at their
startup values. Read this failure as a bad instance, never as a bad plugin
(`references/CONSTRAINTS.md`).

## Mandatory level by change class

| change | mandatory | plus |
|---|---|---|
| Refactor, logging, no user-visible effect | **L2** on one affected route | L0 |
| Model contents — metadata, rows, search results | **L3** on the named props | L0, error-delta grep |
| Navigation or routing | **L2** including expected `currentpage.url` | L0 |
| `.view` | **L4** before/after | never the reload exit code alone |
| Settings or kvstore | **L3** on the setting prop, **and a second run** proving it survived the restart | L0 |
| Playback | the named media sub-level; **L4 for anything with video** | a standalone probe first, when the protocol has one |
| Crash or hang | no level applies — preserve command, log tail, screenshot, exit status | do not repeat the failing smoke |
| Unchanged plugin, newer core | **L2** | the `mdev doctor` line for both cores |

L0 is the cheapest real bug filter and costs nothing, so it is listed as *plus*
rather than optional. Its limits are exact and worth knowing before trusting a
clean result — see the `movian:api` skill.

## Not acceptable as proof

Consolidated; each is explained where it is listed.

1. **HTTP 200, or an `eventSink` `OK`** — transport only (above).
2. **`loading == 0` alone** — page-ready trap (above).
3. **A clean `mdev reload`/`preview` exit for a `.view` syntax change** — the
   lexer blind spot (above).
4. **A matching screenshot hash as evidence of *no* change** — identity only
   (above).
5. **A clean `tsc` as evidence a call is correct** — declarations are `any`-heavy
   and arity-free by design (`movian:api`).
6. **A member missing from the `.d.ts` as evidence of a bug** — modules mutate
   their own exports at runtime (`movian:api`).
7. **A fixed `sleep` followed by a read** — wait for the prop that proves the
   flow (above).
8. **Log silence**, when you never grepped the delta (above).
9. **One run of anything that talks to a remote service** — see below.
10. **"It worked on my core"** — without recording which core.

## Where plugin verification differs from core verification

The rules above are mostly the core's, and they transfer. Four things do not.

**The core is a variable too.** A core change is verified against a tree you
own; a plugin is verified against a core the plugin author does not control and
the plugin user will not match. A red run can mean the plugin is wrong, or that
this core predates the API it calls. Record the provenance with the verdict —
one line of `mdev doctor` gives checkout, HEAD, binary build time and distance
from `origin/movian6`. A verdict without it is not reproducible by anyone else.

**The usual cause of a red run is not your change.** Core smokes fail from the
code under test. Plugin smokes mostly fail from the far end of an HTTP call —
schema drift, expired token, geo-block, rate limit — and every one of those
presents as a plugin bug. Before calling it one, run the **control**: the same
smoke on the unchanged code, or the same request outside Movian with `curl`. A
failure that reproduces without your change is not your change.

**There is no regression suite, and the plugin cannot ship one.** `mdev smoke`
runs declarative JSON smokes, but discovery is core-only: `SMOKES_DIR` is
hardcoded to `<core>/support/devtools/smokes`, and a relative `needs.plugin`
resolves against the core root, not the plugin repo. So a plugin's smokes
currently have to be written into somebody else's checkout
([movian#164](https://github.com/Buksa/movian/issues/164)). Until that is fixed,
keep the smoke as a script in the plugin repo and run it by hand — do not add
plugin smokes to the core.

**Nothing needs rebuilding, so re-verify per edit.** Plugin JS and `.view` reload
into a live instance, which makes verification cheap enough to run after each
edit instead of batching it to the end. It also removes a whole class of core
explanation: a stale build is never why a plugin change did not take.

## Stop blind waiting at 120 seconds

If a UI action, popup, route transition, render or playback wait exceeds two
minutes, stop. Save URL, title, loading, node count, popups, a screenshot and the
last 120–200 log lines, then ask the user to perform one exact manual action
while you keep observing. Do not spin indefinitely.

## References

- `references/test-rules.md` — pass criteria, prop rules, popup rules, visual tests
- `references/CONSTRAINTS.md` — known bad patterns: process, launch, HTTP, timing
- `references/debug-flags.md` — launch and debug flags, dev-flag seeding
- `references/prop-debugging.md` — `/api/prop` internals, `prop.print`, ES stats
- `references/httpcontrol-stpp.md` — HTTP Control matrix, STPP protocol, known defects
- `references/media-playback-smoke.md` — playback evidence levels
- `references/glw-async-focus.md` — deterministic focus on async-loading pages
- `references/glw-pointer-touch-smoke.md` — pointer/touch/kinetic-scroll matrix
- `references/plugin-type-patterns.md` — what to exercise per plugin type: media
  source, protocol, UI/skin, service integration, native/compiled
