---
name: verify
description: Judge whether a Movian plugin change actually works — what counts as proof, what counts as noise, and how much verification a change needs. Use when asked to smoke-test a plugin change, verify a route/prop/screenshot really changed, decide whether a fix is proven, diagnose a false pass or a false failure, or choose the minimum evidence for a change. Mechanics of launching and driving Movian live in the run skill.
---

# Verifying a Movian plugin change

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

## Verification minimums by change class

- **Plugin JS change** — `node --check`, `git diff --check`, a focused smoke of
  the affected route, a screenshot when the change is visual, and a log grep for
  new JS/GLW/image errors.
- **`.view` change** — before/after screenshot, plus the reload false-green
  caveat above. A clean exit code alone is never sufficient for anything touching
  quoting or lexing.
- **Media/protocol change** — prove the specific layer under test: `routed`,
  `probed`, `decoded` or `rendered` (see `references/media-playback-smoke.md`).
  That a URL dispatched proves only routing.
- **Crash or hang** — preserve artifacts (command, log tail, screenshot, exit
  status) instead of repeating the same failing smoke.

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
