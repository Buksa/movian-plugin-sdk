# HTTP, caching and failure handling across the nine plugins

> **Point-in-time survey — read the canon, not this, for current rules.**
> Investigated on the date stated below against the checkouts as they then stood. It is
> the measurement record behind
> [`movian:authoring`](../plugins/movian/skills/authoring/SKILL.md), not a substitute for
> it. Where the two disagree the skill wins: it has been corrected by later measurement
> and by running the code, and this file is deliberately **not** rewritten to match, so
> the reasoning that produced a wrong rule stays visible. Known corrections carried by
> the skill and not by these surveys: a cache hit also arrives as **HTTP 304**, bypassing
> a poisoned entry needs `cacheTime` **deleted** rather than `caching: false`, the
> success check should accept the **2xx range**, `noFail` **does** cover 401 on a current
> core, and route priority has no reachable `INT32_MAX` case.

> **anilibria moved after this was written.** Its `lib/api.js` was 282 lines on
> 2026-08-05, the tree measured here. On **2026-08-08** commit `c39d44a` split it: the
> HTTP transport, the inspector, the TTL constants and the cache-hit check now live in
> `lib/transport.js` (95 lines), and `lib/api.js` is down to 71. Every `lib/api.js` line
> number below is correct as of 2026-08-06 and will not resolve in a current checkout —
> read them with `git show 3802256:lib/api.js`. Nothing in the findings changes; the code
> moved, it did not change behaviour.

Research for [issue #21](https://github.com/Buksa/movian-plugin-sdk/issues/21),
part of the authoring-canon map [#19](https://github.com/Buksa/movian-plugin-sdk/issues/19).
Investigated 2026-08-06.

**Sources.** Two kinds, marked throughout:

- **[CORE]** — `/home/uzver/movian-public-clean`, read-only. `src/ecmascript/es_io.c`,
  `src/fileaccess/fileaccess.c`, `src/fileaccess/fa_http.c`,
  `res/ecmascript/modules/movian/http.js`. This is what actually consumes `ctrl`.
- **[PLUGIN]** — the nine checkouts under `/home/uzver/`. Read-only; nothing was modified.

Claims are **[MEASURED]** (read off a cited line) or **[INFERRED]** (a conclusion drawn
from measured lines, labelled as such). Every measured claim carries `file:line`.

---

## 0. Headline answers

**Why the heaviest user of the API cache built another cache on top.** Not because the
API cache is slow or small. Because it is the *wrong kind of cache* for three things
HDRezka needs, and each gap is a line of C:

1. **It only caches GET with no body.** `es_io.c:163-166` routes a request through the
   caching path (`fa_load`) only when `ehr_cache && method is NULL-or-GET &&
   !headRequest && postdata == NULL`. Everything else goes to `http_req` with no cache
   at all. HDRezka's episode and stream lists are `POST /ajax/get_cdn_series/`
   (`api/rezka.js:94-97`, `:109-113`) — structurally uncacheable by the core. The author
   knew: `api/rezka.js:100` logs `'fromCache=' + fromCache + ' (POST - should be false)'`.
2. **It caches bytes, not meaning.** `es_io.c:224-226` copies the raw buffer into
   `res.buffer`; the plugin still runs `res.toString()`, `dom.parse()` and the whole
   parser on every hit (`api/rezka.js:34-49`). For a 12-season episode tree that is the
   expensive half. HDRezka's own cache stores the *parsed* object
   (`cache/episodes.js:17-19`, keyed `id + ':' + translatorId`).
3. **It is keyed by URL, and only by URL.** `fileaccess.c:1622-1641` folds query args
   into the URL string and `fileaccess.c:1658-1659` calls `blobcache_get(url, ...)`. Nothing
   else enters the key — not headers, not cookies, not method, not auth. HDRezka's
   domain keys are content identities (`translatorCache.generateKey`,
   `utils/cache.js:143-146` returns `'tr:' + contentType + ':' + contentId`), which
   no URL expresses.

A fourth gap is subtler and is the one that actually *bit*: **the core caches by HTTP
status, not by semantic validity.** `fileaccess.c:1742` stores whenever
`*protocol_codep < 300`. An Anubis anti-bot interstitial is served with 200, so the core
caches it, and every subsequent request is served the poison. HDRezka has explicit
recovery code for exactly this — `api/requestPipeline.js:155-159` detects an anti-bot
page that came *from cache* and re-issues with `caching: false`.

**Is the split need or knowledge?** Both, and they are separable — see §5. The short
form: **`caching: true` on its own is advisory and, in two of the five plugins that set
it, provably inert; `cacheTime: N` is the only imperative form, and only two plugins
found it.** That is a knowledge gap, and it is a knowledge gap the core created by
making the weaker spelling the obvious one.

---

## 1. Corrections to the brief

The ticket's starting numbers do not survive checking. Four are wrong.

| claim in #21 | measured | verdict |
|---|---|---|
| six of nine pass `cacheTime`/`caching` | **five** of nine | wrong |
| m7-jellyfin 3 sites | **0** runtime sites | wrong — see below |
| tmdb 1 site | **0** runtime sites | wrong — see below |
| dailymotion none | **2 sites**, `src/ts/support/api.ts:55` and `:68` | wrong |
| HDRezka 24 sites | **13** production sites (+11 in `tests/`) | wrong |
| anilibria 4 | **3** lines, **1** call path (`lib/api.js:102,116,117`) | close enough to restate |
| trakt 3 | **4** (`src/api.js:76,200,337,348`) | minor |
| youtube 1 | 1 (`api.js:174`) | correct |
| qobuz none, soap4.me none | correct | correct |
| HDRezka ~15 own-cache files | **exactly 15** | correct |

- **m7-jellyfin never passes either flag at runtime.** All eight hits are in hand-written
  type declarations: `libs/movian/http.d.ts:18,19,33,34`, `libs/native/io.d.ts:53,56`,
  `libs/native/faprovider.d.ts:94`. Its eleven real call sites
  (`src/api.js:65,97,116,176,220,239,259,279,317,331` and `src/upgrader.js:43`) pass no
  cache flag. It *documented* the feature and never used it.
- **tmdb's only occurrence is inside a commented-out block.** `tmdb.js:1329` sits
  between `/*` at `:1327` and `*/` at `:1331`. The live call immediately above it is
  `tmdb.js:1324-1326`: `showtime.JSONDecode(showtime.httpGet(url, {}, {'Accept':
  'application/json'}).toString())`. Someone tried the cache, and reverted.

**Methodology note, and it matters for this map.** Naive `grep -rn PATTERN <repo-root>
--include=*.ts` returned **nothing** for `movian-plugin-dailymotion` on this machine,
while `grep -rIn PATTERN <repo-root>/src --include=*.ts` returned both hits. This is how
dailymotion was recorded as a non-user. The reliable form, used for every count above,
is `find <repo> -prune-noise -print0 | xargs -0 grep -n`. Map #19 already warns that a
wrong identifier produces a wrong finding; this is the sibling failure — a *right*
identifier and an unreliable traversal. Counts in this corpus should be taken with
`find | xargs`, and build outputs (`build/`, `build-swc/`, `build-min/`, `dist/`,
`releases/`) and `tests/` excluded explicitly, or an author's intent gets counted twice
from a bundle.

**Corrected split — five who set a cache flag, four who do not:**

| sets a cache flag | sets none |
|---|---|
| HDRezka, anilibria, trakt, youtube, dailymotion | qobuz, m7-jellyfin, tmdb, soap4.me |

---

## 2. What the core actually does with `ctrl` [CORE]

The JS wrapper is thin. `res/ecmascript/modules/movian/http.js:80-90` merges an
`args` array into one object; `:93` decides sync vs async purely on whether a third
argument was passed; `:95-99` shows the callback is **error-first — `function(err, res)`**,
with `callback(err, null)` at `:97` on failure and `callback(null, new HttpResponse(res))`
at `:99` on success. Without a callback, `:103-104` returns an `HttpResponse`
synchronously and a failure *throws*.

Everything else is `es_io.c:es_http_req`. The recognised `ctrl` fields, with their line:

| field | line | effect |
|---|---|---|
| `debug` | `es_io.c:305` | `FA_DEBUG` |
| `noFollow` | `es_io.c:306` | `FA_NOFOLLOW` |
| `compression` | `es_io.c:307` | `FA_COMPRESSION` (sends `Accept-Encoding: gzip`) |
| `noAuth` | `es_io.c:308` | `FA_DISABLE_AUTH` |
| `noFail` | `es_io.c:309` | `FA_CONTENT_ON_ERROR` |
| `verifySSL` | `es_io.c:310` | `FA_SSL_VERIFY` |
| `headRequest` | `es_io.c:312` | HEAD |
| **`cacheTime`** | **`es_io.c:313`** | `ehr_min_expire`, seconds |
| **`caching`** | **`es_io.c:314`** | `ehr_cache`, **or'd with `cacheTime != 0`** |
| `headers` | `es_io.c:319-339` | request headers |
| `postdata` | `es_io.c:341-388` | buffer (`:343`) / object, form-encoded (`:351`) / string (`:377`) |
| `args` | `es_io.c:394-398` | query args |
| `method` | `es_io.c:404-408` | verb |

### 2.1 `caching: true` is advisory. `cacheTime: N` is imperative.

Three lines produce this, and no plugin documentation states it.

**(a) Any custom header silently vetoes `caching: true`.**

```c
es_io.c:414   if(ehr->ehr_cache && ehr->ehr_min_expire == 0)
es_io.c:415     ehr->ehr_cache = !disable_cache_on_http_headers(&ehr->ehr_request_headers);
```

and `disable_cache_on_http_headers` (`es_io.c:145-154`) returns 1 if the request carries
**any** header whose name is not `user-agent`. So `caching: true` + one `Accept` header =
no caching, no warning, no log line. The veto is skipped entirely when `cacheTime` is
non-zero — that is what `ehr_min_expire == 0` guards.

**(b) Without `cacheTime`, the origin server decides whether anything is stored at all.**
`fileaccess.c:1742-1744` only calls `blobcache_put` when
`data2 && cache_control != DISABLE_CACHE && *protocol_codep < 300 && (cache_control ||
max_age || etag || mtime)`. `max_age` comes from the response:
`fa_http.c:2317-2323` reads `Date`/`Expires`, `fa_http.c:2325-2327` reads
`Cache-Control: max-age=`, and `fa_http.c:2330-2332` **zeroes it on `no-cache` or
`no-store`**. An API that says `Cache-Control: no-store` and sends no ETag defeats
`caching: true` completely.

**(c) `cacheTime` overrides all of that.** `fileaccess.c:1741` is
`max_age = MAX(min_expire, max_age);` — evaluated *after* the `no-cache` zeroing at
`fa_http.c:2331`. `cacheTime` therefore forces a minimum lifetime **even against an
origin that asked not to be cached**. That is real power and a real hazard, and it is
undocumented in both directions.

[INFERRED] The naming is backwards from the behaviour. `caching` reads like the switch
and `cacheTime` like the tuning knob; in fact `cacheTime` is the switch (it implies
`caching` at `es_io.c:314`) and `caching` alone is a request the core may decline.

### 2.2 The undocumented cache-hit signal: `statuscode === 0`

`fileaccess.c:1621` sets `*protocol_codep = 0` before anything else. The fresh-from-cache
early return at `fileaccess.c:1673-1680` never assigns it. `es_io.c:242-243` then pushes
`ehr_http_status` as `res.statuscode`. So **a response served from the blob cache arrives
with `statuscode === 0`, and `err` is null.**

This is nowhere in `movian/http.js`. Three independent authors found it anyway:

- HDRezka — `api/requestPipeline.js:103` `var isCache = res.statuscode === 0;`
- anilibria — `lib/api.js:126` `var cacheHit = (res.statuscode === 0);`
- soap4.me's successor-in-style dailymotion — `src/ts/support/http.ts:80-83`,
  `if (statuscode == 0) { // response from cache`

All three then had to special-case it in their status check, because a naive
`statuscode !== 200` treats every cache hit as a failure — see
`api/requestPipeline.js:104` and `lib/api.js:128`. **This is the single strongest
convergence finding in the survey, and it is convergence on working around a defect.**

### 2.3 The cache is not scoped to the caller's identity

`fileaccess.c:1658-1659` keys on `url` alone; headers, cookies and `Authorization` never enter
the key. [INFERRED] A plugin that enables caching on an authenticated, per-user endpoint
would serve one account's data to another after a credential switch within the same
install. No plugin in the corpus demonstrably hits this — trakt would, but its caching is
inert (§3.3) — so this is a hazard, not an observed bug.

---

## 3. Per-plugin findings

| plugin | issues requests | cache flags | failure handling | retry | rate limit / auth challenge |
|---|---|---|---|---|---|
| **HDRezka** | async error-first, exclusively | `caching`+`cacheTime`, 13 sites | error string via `cb(err)`; `noFail` on every request | yes — anti-bot re-attempt loop | `httpInspectorCreate` + Anubis proof-of-work; self-imposed pagination delay |
| **trakt** | async error-first (API), **sync** in the auth path | `caching: true` ×4, **inert** | inverts the callback: `cb(json, pagination)` / `cb(null, null, err)` | yes — token refresh + device login inside the inspector | `httpInspectorCreate` on 401; **429 additive backoff** |
| **anilibria** | async error-first | `caching`+`cacheTime`, per-endpoint TTLs | `callback(new Error(...))` | no — but DNS mirror failover | `httpInspectorCreate` for UA/Referer/`cf_clearance` |
| **youtube** | async error-first | `caching: true` ×1 | `page.error(err)`, then `throw` | no | none — API key in query args |
| **dailymotion** | both, chosen by argument | `caching: true`, toggled off by config | typed `SUCCESS`/`ERROR` union, `throwOnError` config | no | none |
| **qobuz** | **sync**, throws | none | translates status to a specific `Error` | no | **429 named explicitly**; `httpInspectorCreate` for 401 |
| **m7-jellyfin** | **sync** | none | `if (response.statuscode == 200)` and little else | no | none — token in header, no 401 path |
| **tmdb** | **sync**, global `showtime.httpGet` | none (commented out) | `try/catch`, `return null` | no | recognises HTTP 503 as "too many connections" |
| **soap4.me** | **sync** | none | `if (response.statuscode !== 200)` → notify + redirect | no | none |

### 3.1 HDRezka — the deep one

Every request funnels through one function. `api/requestPipeline.js:78-114` builds `ctrl`
with a fixed shape: `method` (`:80`), computed `headers` (`:81`), `compression: true`
(`:82`), **`noFail: true` (`:83`)**, and cache flags only if the caller asked (`:86-89`).
POST bodies are hand-form-encoded at `:91-98` rather than handed to the core's object
path — [INFERRED] because the core's encoder (`es_io.c:351-375`) does not let the caller
set the `charset` on the content type, which HDRezka does at `:97`.

Failure is a **plain string**, not an `Error`: `:102` `if (err) return cb(err)`, `:104`
`return cb('HTTP ' + res.statuscode)`, `:127` `return cb('JSON Parse error')`. `noFail`
means the core returns bodies for 4xx/5xx rather than raising, so the status check at
`:104` is the real error gate — and it has to exempt `statuscode === 0`.

Retry is the anti-bot loop, `api/requestPipeline.js:132-179`. A three-state machine
(`initial` → `fresh` → `postChallenge`, `:139`, `:156`, `:166`):

- anti-bot page **from cache** → retry with `caching: false` (`:155-158`)
- anti-bot page **fresh** → solve the Anubis proof-of-work, then retry (`:161-175`)
- anti-bot page **after solving** → give up (`:150-153`)

The challenge solver itself issues a `noFollow: true` request and reads `Set-Cookie` off
the 302 (`api/anubisChallenge.js:88-110`), with cookies injected through a global
inspector (`utils/httpInspector.js`, 252 lines). That inspector exists because inspectors
decorate requests the plugin never makes — the media URLs the player opens directly.

Rate limiting is **self-imposed and cache-aware**: `pages/catalog.js:33-37` delays
`haveMore()` by `CACHE_PAGINATION_DELAY` *only when the page came from cache*, because a
cached page returns instantly and would otherwise let the UI's infinite scroll fire the
next fetch immediately.

### 3.2 HDRezka's second (and third) cache

Three layers, all live at once:

1. **Core blob cache** — disk, bytes, URL-keyed, GET-only (§2).
2. **In-process TTL map** — `utils/cache.js:20-133`, a `createCache({prefix, ttl,
   maxSize})` factory. `get` expires on read (`:43-48`), `set` evicts the oldest half at
   `maxSize` (`:64-74`). Instantiated as `cache/episodes.js:7-11` (5 min, key
   `id + ':' + translatorId`) and, inside the bundled TMDB client, as a hand-rolled
   equivalent at `utils/tmdb_module/tmdb-simple.js:55-80` (30 min).
3. **Persistent store** — `cache/translators.js:5,18-23`, `movian/store` with
   `JSON.stringify`/`JSON.parse`, keyed by content id, **no TTL**, survives restart.

The clearest single exhibit is `utils/tmdb_module/tmdb-simple.js`, which caches the
**same data twice**: `:188-190` sets `caching: true, cacheTime: 1800`, and `:158` also
does `this.setCached(cacheKey, result)` with the same 30-minute TTL at `:67-80`. That is
not redundancy. The core cache returns bytes that must be re-parsed; `getCached`
(`:55-63`) returns the parsed object. The two caches store different things about one
response.

### 3.3 trakt — `caching: true` that provably does nothing [MEASURED]

Every API call goes through `Api.call` (`src/api.js:46`), which unconditionally sets
three headers before the request:

```js
src/api.js:68   opts.headers = opts.headers || {};
src/api.js:69   opts.headers['Content-Type'] = "application/json";
src/api.js:70   opts.headers['trakt-api-key'] = api.CLIENT_ID;
src/api.js:71   opts.headers['trakt-api-version'] = 2;
...
src/api.js:76   opts.caching = true; // Enables Movian's built-in HTTP cache
```

No call site sets `cacheTime`. So `es_io.c:414` sees `ehr_min_expire == 0`, `es_io.c:415`
calls `disable_cache_on_http_headers`, which hits `Content-Type` at `es_io.c:151` and
returns 1 — `ehr_cache` becomes 0. **`opts.caching = true` at `src/api.js:76`, and the
three per-endpoint repeats at `:200`, `:337`, `:348`, are dead.** The comment on `:76` is
sincere and wrong.

trakt is otherwise the corpus's best auth work. `src/api.js:10-42` registers
`io.httpInspectorCreate('https://api.trakt.tv/.*', ...)` which:

- skips `/oauth/` to avoid a loop (`:12-16`)
- attaches `Authorization` when a token exists (`:19-24`)
- on `ctrl.authFailed`, clears the token, tries `auth.refreshToken()` (`:29-36`), and
  falls back to a full device-code login (`:39-42`)

The device-code poll in `src/auth.js` is the **only real rate-limit backoff in the
corpus**: `:47` takes the server's `interval`, `:93-96` on `statuscode === 429` adds
1000ms and re-arms the timer. Note that `auth.login` itself uses a **synchronous**
`http.request` (`src/auth.js:11-21`) called from inside the async inspector callback.

trakt is also the only plugin that **discards the error-first shape entirely**: its own
callback is `callback(json, pagination)` on success (`src/api.js:126`) and
`callback(null, null, error)` on failure (`:98`, `:102`). A reader coming from
`movian/http.js` will get the argument order wrong.

### 3.4 anilibria — the cleanest cache use

`lib/api.js:102-142` is one request function with an explicit TTL parameter. `:116-117`
sets `opts.caching = true; opts.cacheTime = cacheTime || CACHE_CATALOG;` — and because
`cacheTime` is non-zero, the header veto at `es_io.c:414` is skipped, so its
`Accept`/`Content-Type`/`User-Agent` headers (`lib/api.js:20-24`) do **not** kill the
cache. TTLs are per endpoint and named: `CACHE_CATALOG` 120s, `CACHE_RELEASE` 300s,
`CACHE_SCHEDULE` 60s, `CACHE_FRANCHISE` 600s (`lib/api.js:10-13`), applied at `:163`,
`:173`, `:185`, `:201`, `:210`.

It also returns cache provenance to its callers — `callback(null, {data, cacheHit})`
(`:135-138`) — the same design decision HDRezka made with its third callback argument.

No retry. Instead, **failover**: `discoverMirror` (`lib/api.js:45-74`) resolves a TXT
record through `https://dns.google/resolve` and rewrites `BASE_URL` before the first
request. Its inspector (`lib/api.js:30-42`) sets `User-Agent`, `Referer`, `Origin` and a
`cf_clearance` cookie — Cloudflare, handled by impersonation rather than by challenge.

### 3.5 youtube — the author's own plugin, and the reference shape

`api.js:168-176` is the intended idiom, comments and all: `args` as an **array of
objects** to be merged (`:171` — the feature `movian/http.js:80-90` exists to serve),
`noFail`, `compression`, `caching`, and `verifySSL` commented out at `:175`. No headers
at all, so `caching: true` survives the veto — [INFERRED] andoma wrote the call the way
the core wants it, without needing to know about the veto, because he never added
headers.

Failure handling is the shortest in the corpus and routes into the page:
`api.js:180-183` on transport error → `page.error(err)`; `:186-193` inspects the JSON
body for `r.error` and calls `page.error(r.error.errors[0].reason)`. No retry, no
rate-limit handling. [INFERRED] The reference implementation demonstrates the API but
does not demonstrate resilience — which is why the other eight had to invent it.

### 3.6 qobuz — maximum knowledge, zero caching

qobuz is the decisive case for §5. Its comments **cite core line numbers**:
`lib/inspector.js:12-18` explains that a matching inspector sets `hf_ext_auth`
(`fa_http.c:1030`) so `authenticate()` takes the external-inspector branch
(`fa_http.c:1502`) instead of dying with "Authentication without realm", and that
inspectors are skipped under `noAuth` (`fa_http.c:3115`). `lib/qobuz.js:85-90` records
that `noFail` does **not** cover 401 because `case 401` is handled ahead of the `default`
branch — **true when that comment was written, and no longer true**: core #149 / PR #154
made `case 401` honour `FA_CONTENT_ON_ERROR`, so `noFail` covers 401 on a current core.
Read the qobuz comment as a historical record of the core it was written against. `lib/inspector.js:34-37` notes that Movian stops at the first matching inspector
and the list is head-inserted, so the two patterns must be mutually exclusive.

This author read `es_io.c` and `fa_http.c` line by line — and set **no cache flag
anywhere**. Requests are synchronous (`lib/qobuz.js:93-98`, `lib/bundle.js:20`), with
`noFail: true` (`:95`) and `compression: true` (`:96`) and nothing else. Failure is translated into
specific messages by status: 401 → "the User Auth Token is missing or expired"
(`:122-124`), **429 → "Qobuz rate limit reached — try again shortly"** (`:125-126`),
otherwise the API's own `body.message` verbatim (`:113-120`). No retry: it throws.

### 3.7 m7-jellyfin — types over the cache it never uses

Eleven synchronous `http.request` calls, every one with custom headers
(`src/api.js:55-60` builds `Content-Type`/`Authorization`/`X-Emby-Token`), none with a
cache flag. Failure handling is `if (response.statuscode && response.statuscode == 200)`
and an implicit "return whatever it was otherwise" (`src/api.js:80`, `:105`, `:124`, and six more through `:336`). `try/catch` appears
once, around `authenticate` (`src/api.js:62-85`), and it is unsound: `response` is
assigned inside the `try` at `:65` and read at `:80` outside it, so a throw inside the
`try` produces a `TypeError` at `:80` — the `catch` at `:76-78` logs and falls through.
Two other call sites have the `try/catch` **commented out** (`src/api.js:96`+`:101`,
`:115`+`:120`). No retry, no 401 recovery.

It nonetheless carries the corpus's most complete hand-written declarations of the very
fields it does not pass (`libs/movian/http.d.ts:18-34`, `libs/native/io.d.ts:53-56`).

### 3.8 tmdb — the global-`showtime` era

Requests are `showtime.httpGet(url, args, headers)` and `showtime.httpReq(url, ctrl)` —
15 occurrences in `tmdb.js`, all synchronous, no `require` anywhere. The live API call is
`tmdb.js:1324-1326`, wrapped in a `try/catch` that returns `null` on any failure
(`:1335-1340`). The 503 case gets a diagnostic string — `:1337-1338`, `if (ex == "Error:
HTTP error: 503") t("There is a big number of simultaneous connections")` — the corpus's
only acknowledgement of server-side overload outside qobuz's 429. And the `caching: true`
attempt is right there at `:1329`, commented out.

### 3.9 dailymotion — the typed wrapper

`src/ts/support/http.ts:35-71` wraps `http.request` in a small algebraic result type
(`HttpCallbackResult = Success | Error`, `:7-24`), forces `opts["noFail"] = true` on every
call (`:38`), and supports **both modes from one signature** — callback given → async
(`:42-59`), callback omitted → sync (`:63-70`). Whether an error throws or is delivered
to `onError` is a caller-supplied `config.throwOnError` (`:52-55`, `:66-67`). The
`statuscode == 0` cache case is classified as success at `:80-83`.

`src/ts/support/api.ts:52-55` sets `compression: true, caching: true` for every API call,
with `:67-68` letting a caller opt out. No headers are set, so — like youtube — the veto
does not fire. No `cacheTime`, so storage is at Dailymotion's discretion. No retry, no
429 handling.

### 3.10 soap4.me — a JS cache instead of the API's

Seven synchronous `request(...)` calls (`src/index.js:85, 105, 189, 288, 312, 328, 383`),
all `method`/`noFollow`/`headers`, none with a cache flag. Failure handling is a bare
status check plus a UI action — `src/index.js:390-393`: `if (response.statuscode &&
response.statuscode !== 200) { notify(i18n.LoginError); return page.redirect(...) }`. No
retry, no 429, no 401 recovery.

And yet it caches. `src/index.js:81` is `const cache = {};`, filled by
`dataHandlers.series.load()` (`:84-97`) and `dataHandlers.seasons.load(sid)`
(`:105-...`), read by `dataHandlers.seasons.get(sid)` (`:100-102`). A plain object memo,
no TTL, no bound, process-lifetime only. **The plugin whose author had never seen the
platform before built a cache by hand while the platform's own cache sat one `ctrl` field
away.** No knowledge of `caching` appears anywhere in the repo.

---

## 4. Convergence and divergence

**Converged, without contact:**

- **`noFail: true` on essentially every request** — HDRezka `requestPipeline.js:83`,
  trakt `api.js:74`, youtube `api.js:172`, qobuz `qobuz.js:95`, dailymotion
  `http.ts:38`. Five of nine, five different authors. [INFERRED] The default — throw, or
  hand back an error with no body — makes an API's own error message unreadable, so
  everyone turns it off.
- **`compression: true`** — HDRezka `:82`, trakt `:75`, youtube `:173`, qobuz `:96`,
  anilibria `lib/api.js:111`, dailymotion `api.ts:54`. Six of nine.
- **`statuscode === 0` means "from cache"** — HDRezka `requestPipeline.js:103`, anilibria
  `lib/api.js:126`, dailymotion `http.ts:80`. Three of three plugins that both cache and
  check status. Nobody could have read this anywhere.
- **Cache provenance is propagated to callers** — HDRezka's third callback argument
  (`requestPipeline.js:112`, threaded through `rezka.js:31,50` into `pages/catalog.js:123`
  where it changes pagination timing), anilibria's `{data, cacheHit}` (`lib/api.js:135-138`).
- **`io.httpInspectorCreate` is the answer to auth and to bot-defence** — trakt
  `api.js:10`, HDRezka `utils/httpInspector.js`, anilibria `lib/api.js:30`, qobuz
  `lib/inspector.js`. Four of nine, for three unrelated problems (OAuth 401, Anubis
  cookies, Cloudflare impersonation). It is not in `movian/http.js` at all — it is on
  `native/io`, and every one of them had to reach past the documented module to find it.

**Diverged:**

- **Sync vs async.** Async-only: HDRezka, anilibria, youtube. Sync-only: qobuz,
  m7-jellyfin, tmdb, soap4.me. Both: trakt (async API, sync auth), dailymotion (one
  function, chosen by argument). Four-five-ish, with no correlation to age, authoring
  style, or transpiler. [INFERRED] The API offers both with equal prominence
  (`movian/http.js:93-104`) and says nothing about which to prefer, so authors picked by
  taste. This is the largest unforced divergence in the survey.
- **The error value.** A string (HDRezka), an `Error` (anilibria, qobuz), a typed union
  (dailymotion), a third callback parameter in reversed position (trakt), `null`
  (tmdb, and youtube's `page.error` path).
- **Where a failure surfaces.** Into `page.error` (youtube `api.js:182`), into a `notify`
  + redirect (soap4.me `:391-392`), as a thrown `Error` (qobuz), or back up the callback
  chain (HDRezka, anilibria).

---

## 5. Need, or knowledge?

Both, and the corpus separates them cleanly because the two extremes are unambiguous.

**Need is real, and it explains the two non-cachers at the top of the knowledge scale.**

- **qobuz** demonstrably read the C (§3.6) and cached nothing. Its endpoints are signed,
  per-user, and return short-lived file URLs; a URL-keyed byte cache is not merely
  useless there, it is unsafe (§2.3). **Need.**
- **m7-jellyfin** talks to the *user's own server* on the LAN, with per-user tokens. Its
  `.d.ts` files (`libs/movian/http.d.ts:18-34`) prove it knew the fields existed.
  **Need** — round-trips are cheap and freshness matters.

**Knowledge is the rest of the story, and it is not close.**

- **soap4.me** hand-rolled `const cache = {}` (`src/index.js:81`) rather than set one
  field. Nothing in the repo mentions `caching`. **Knowledge.**
- **tmdb** tried `caching: true` and commented it out (`tmdb.js:1329`), keeping the
  `showtime.httpGet` call above it — which passes an `Accept` header (`:1325`) and would
  therefore have been vetoed by `es_io.c:415` anyway. [INFERRED] It plausibly *did not
  work when tried*, for exactly that reason, and was reverted as broken rather than
  diagnosed. **Knowledge, defeated by an invisible veto.**
- **trakt** believes it caches, comments that it caches, and does not cache
  (§3.3). **Knowledge.**
- **youtube and dailymotion** set `caching: true` with no `cacheTime` and no headers, so
  the cache is live but its lifetime is entirely the origin's choice. Neither shows any
  sign of knowing that `cacheTime` would make it deterministic. **Partial knowledge.**
- Only **HDRezka and anilibria** — two of nine — use the imperative form. Both also
  discovered `statuscode === 0` on their own, which is what using it forces you to learn.

So the split is **not** five who needed caching against four who did not. It is **two who
found the working spelling, three who found a spelling that is advisory or inert, and
four who did not look — of whom only two had a reason not to.**

[INFERRED] The core is the proximate cause. It offers two spellings where the weaker one
is the obvious one; it makes the stronger one look like a tuning parameter for the weaker
one; it silently voids the weaker one on any header, which is the first thing a real API
client adds; and it signals a cache hit with a status code that every naive success check
rejects. Three of five cache-users got a worse result than they thought they had, and one
non-user probably tried and was defeated. That is a documentation failure the canon can
fix with one paragraph.

---

## 6. What the canon should say

Each rule has a plugin and a line behind it.

1. **Use the error-first callback form. Reserve synchronous requests for start-up.**
   The signature is `function(err, res)` (`movian/http.js:97`). Sync requests block the
   Duktape context; m7-jellyfin (`src/api.js:65`) and soap4.me (`src/index.js:85`) block
   on every page load. Model: `api/requestPipeline.js:101-113`.
2. **Set `noFail: true`.** Without it, an API's own error body is unreachable. Five of
   nine converged on this unprompted (§4).
3. **Then check `statuscode`, exempting `0`.** `noFail` moves the error gate into your
   code. `res.statuscode === 0` means "served from cache", not "failed" — `es_io.c:243`
   + `fileaccess.c:1621`. Model: `api/requestPipeline.js:103-104`.
   > **Superseded — do not copy this rule.** It is incomplete in two ways found after
   > this survey was written: a cache hit also arrives as **`304`**
   > (`fa_http.c:3187`, `fileaccess.c:1701-1709`), and the check should accept the whole
   > **2xx range**, not `200` alone. The canon carries the corrected form; a plugin
   > written to the rule as stated here shows an error page on a revalidated cache hit.
   > Measured — it is how core #181 was found.
4. **To cache, pass `cacheTime` — never `caching` alone.** `caching: true` is vetoed by
   any non-`user-agent` header (`es_io.c:414-415`, `:145-154`) and, if it survives,
   stores nothing unless the origin permits (`fileaccess.c:1742`). `cacheTime: N` skips
   the veto and forces a floor (`fileaccess.c:1741`). Model: `lib/api.js:116-117` with
   named per-endpoint TTLs at `:10-13`.
5. **Never cache an authenticated or per-user endpoint.** The key is the URL alone
   (`fileaccess.c:1658-1659`). qobuz's abstention is the model.
6. **The API cache caches bytes, not meaning. Add your own layer for parsed objects, for
   POST results, and for anything keyed by a domain identity.** All three gaps are
   structural (§0). Model: `utils/cache.js:20-133` — a ~110-line TTL factory with
   expire-on-read and size eviction is enough; `cache/episodes.js:13-23` is the whole
   consumer.
7. **A cached 200 is not a valid 200.** The core stores anything under 300
   (`fileaccess.c:1742`), including anti-bot interstitials and login walls. If your
   source can serve those, validate the *body* and retry with `caching: false` on
   failure. Model: `api/requestPipeline.js:145-159`.
   > **Superseded — do not copy the retry.** `caching: false` does **not** bypass a
   > poisoned entry; the read side is driven by `cacheTime`, so the retry must clone the
   > options and `delete` that field. HDRezka's model line has the same defect. The
   > canon carries the working form.
8. **Return cache provenance to callers.** UI pacing depends on it — a cached page
   returns instantly and can trigger runaway pagination
   (`pages/catalog.js:33-37`). Model: `lib/api.js:135-138`.
9. **Headers that must reach the player, and 401 recovery, belong in an
   `io.httpInspectorCreate` inspector — not in `ctrl.headers`.** Media URLs never pass
   through your `http.request` calls (`lib/inspector.js:5-8`). Do not set `noAuth` on a
   request you want an inspector to see (`fa_http.c:3115`, cited at `lib/qobuz.js:80-83`).
   Models: `src/api.js:10-42` (OAuth), `lib/inspector.js` (headers + 401).
10. **Back off on 429.** One plugin in nine does (`src/auth.js:93-96`); one more names it
    (`lib/qobuz.js:125-126`); seven ignore it.

**One core change would retire rules 3 and 4.** Have `es_io.c` log when
`disable_cache_on_http_headers` voids a caller's `caching: true`, and set a real status
code (or an explicit `res.fromCache`) on a cache hit. Both are a few lines, and between
them they account for three of the five wrong or weak cache uses in this corpus. Out of
scope for map #19 — worth filing against the core.

---

## Appendix: verification commands

```sh
# Authoritative site count. Plain `grep -r` under-reports on this corpus (§1).
find <plugin> \( -name node_modules -o -name .git -o -name .codegraph \
  -o -name build -o -name build-min -o -name build-swc -o -name dist \
  -o -name releases \) -prune -o -type f \( -name '*.js' -o -name '*.ts' \) \
  -print0 | xargs -0 grep -n 'cacheTime\|caching'
```

Core files read, all in `/home/uzver/movian-public-clean`:
`res/ecmascript/modules/movian/http.js`, `src/ecmascript/es_io.c`,
`src/fileaccess/fileaccess.c`, `src/fileaccess/fa_http.c`.

Corpus note: `movian-soap4.me` is the one plugin of the nine **without** a `.codegraph/`
index — the brief states all nine are indexed. It was surveyed by direct reading.
