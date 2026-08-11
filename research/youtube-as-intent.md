# andoma's youtube plugin, read as a document

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

Research for [issue #23](https://github.com/Buksa/movian-plugin-sdk/issues/23),
part of the [plugin authoring canon](https://github.com/Buksa/movian-plugin-sdk/issues/19).
Investigated 2026-08-06.

**Sources.** Four kinds, marked throughout:

- **[READ]** — the plugin checkouts on this machine, read-only. Cited `path:line`.
- **[CORE]** — `/home/uzver/movian-public-clean` (source, `glwskins/`, `res/ecmascript/`).
  Cited `path:line`.
- **[HIST]** — `git log` in the core checkout and in
  `/home/uzver/movian-plugin-youtube`. Cited by commit hash and date.
- **[MEASURED]** — counts produced by grepping the nine checkouts with
  `node_modules/`, `.git/`, `dist/`, `build-swc/` and `*.d.ts` excluded.

Inferences are labelled **[INFER]**. The ticket's era-vs-intent constraint is
answered explicitly in §1 and again per-claim; §7 lists what could not be separated.

---

## 0. The headline answer

**youtube is not a plugin written against the API. It is the plugin the API was
written for.** [HIST] The evidence is calendar-tight, and it is the finding that
makes every other one interpretable:

| date | core commit | youtube |
|---|---|---|
| 2016-04-28 | `ed878c718` *ecmascript: Add support for async HTTP inspectors* | — |
| 2016-05-01 | `afb9cc28d` *ecmascript: Add console.error() method* | `9f9f7c0` **Initial** |
| 2016-05-05 | `c4fe01959` *Fix regression with httpInspectors working in synchronous mode* | `bf92157` *Improve how we get current region* |
| 2016-05-20 | `0d2753f82` *Add popup module*, `744053674` *Fix support for action items in plugins*, `63d18a609` *Add support for verifying SSL certificates* | `ab5e151` *Add support for like/dislike buttons* |

The async-inspector feature that `api.js:154` passes `true` to landed in the core
**three days before the plugin's first commit**. The `console.error()` the plugin
calls at `api.js:59`, `api.js:188-189` landed **the same day**. The popup module
(`browse.js:2`), the option-item fix behind `addOptAction` (`browse.js:202`,
`browse.js:213`) and `verifySSL` (`api.js:215`) all landed **on the same day** as
the youtube commit that first uses them. Same author on both sides.

So the plugin's idiom is not "what the API allowed"; it is "what the API was
extended to allow, as the plugin needed it". That is as close to a specification
as this platform has.

**But the plugin also proves that the API outran even its author.** §6 lists four
live defects in it, including one that makes the like/dislike buttons — the very
feature that drove the 2016-05-20 core commits — operate on the wrong list item.
Read it as intent. Do not read it as reference code.

---

## 1. Era versus intent: what the dating actually settles

The ticket's caution is correct but narrower than it looks.

**Era, settled.** [HIST] The `showtime/*` module paths are era, definitively. The
require block at `youtube.js:44-46` was written in `9f9f7c0` (2016-05-01) and
extended in `bf92157` (2016-05-05); the `showtime/` → `movian/` rename is
`3e1fb2fc3`, **2016-05-31**. The lines predate the rename by three-to-four weeks
and were never touched again. [CORE] The compat rewrite at
`src/ecmascript/ecmascript.c:436-437` is what keeps them working. No intent claim
may rest on the spelling.

**Not era.** [HIST] Everything youtube *declines* in §3 existed well before it was
written, so declining it is a choice, not an absence:

| surface | present in the ecmascript API by | youtube written |
|---|---|---|
| `page.Searcher` | 2014-09-21 `83035d7ab` (present at that refactor, possibly earlier) | 2016-05 |
| `settings.createMultiOpt` | ≤ 2014-11-04 `3ba65b460` (that commit is a *rename*) | 2016-05 |
| `httpInspectorCreate` | 2014-10-21 `9ab0e8d02` | 2016-05 |
| `asyncPaginator` | 2015-01-26 `a1c93366e` | 2016-05 |
| `getAuthCredentials` | 2010-10-21 `c6743ca03` (pre-ecmascript, carried forward) | 2016-05 |

**A third category the ticket did not anticipate: era that is *not* an excuse.**
[HIST] The rename shipped 2016-05-31. andoma kept committing to this plugin until
`3600e59`, **2018-03-20** — twenty-two months later — and never migrated the
require paths. [INFER] The compat alias is therefore not a courtesy to third
parties; the author's own plugin is a first-class consumer of it. A canon that
says "always write `movian/*`" is right on style but should not claim the author
agreed.

---

## 2. What the author's plugin does that no one else does

Each row was checked across all nine checkouts. [MEASURED]

### 2.1 `control.uriprefixes` — the only plugin that is reachable from a URL

[READ] `movian-plugin-youtube/plugin.json:14-22` declares seven URI prefixes.
**No other plugin in the corpus declares a single URI prefix.** Seven have no
`control` block at all; m7-jellyfin has `"control": {}` — empty — in its
`package.json` `movian` key. [CORE]
`src/plugins.c:2211-2221` feeds that list to `autoplugin_create()` /
`autoplugin_trigger_add_prefix()` — the on-demand plugin-install trigger. It pairs
with the six raw-URL routes at `youtube.js:301-306` and the four playlist routes at
`youtube.js:156-159`.

The design this expresses: **a plugin is a handler for a URL space, not an app
behind an icon.** Paste a `youtu.be/…` link anywhere in Movian and the plugin is
found, installed and asked to play it. Every other plugin in the corpus is
reachable only through its own home-screen icon.

Safe as intent. [HIST] The prefixes were added deliberately in `ba6aca7`
(2016-08-16, *"Add uri-prefixes to control file"*), three months after the plugin
worked without them.

### 2.2 Async HTTP inspectors, and the correct sync protocol

> **Corrected 2026-08-10.** Two errors here were wrong *when written*, not merely
> stale: the claim that no other plugin passes `true` (trakt does), and the claim that
> anilibria calls `proceed()` in sync mode (it never has — the very lines cited,
> `lib/api.js:31-44` in the tree surveyed, contain no `proceed` call). A citation
> pointing at code that contradicts the sentence citing it is the failure this survey
> should have been proof against. Separately and harmlessly, anilibria was refactored on
> 2026-08-08 — `lib/api.js` split, and its transport now lives in `lib/transport.js` —
> so anilibria line numbers below are correct for 2026-08-06 and do not resolve today.

[READ] `api.js:154` passes `true` as the third argument to
`io.httpInspectorCreate`. **One other plugin passes `true`** — trakt
(`src/api.js:43`). The remaining three pass `false` explicitly: qobuz
(`lib/inspector.js:72`, `:98`), HDRezka (`utils/httpInspector.js:152`, `:223`,
`:247`) and anilibria (`lib/transport.js:34`).

That matters because the two modes have *different protocols*, and two of the three
sync users get theirs wrong. [CORE] `src/ecmascript/es_io.c:796-801`: in **sync**
mode the callback's **return value** is the verdict — `1` means "I did nothing",
anything else means "I handled it". `src/ecmascript/es_io.c:635-645`: `proceed()`
only signals anything when `ehi_async` is set.

- youtube's sync inspector returns explicitly: `youtube.js:50` `return 0;`.
- youtube's async inspector never returns; it calls `ctrl.proceed()`
  (`api.js:22`, `:53`, `:134`) and `ctrl.fail()` (`api.js:125`, `:146`) — the
  async protocol, correctly.
- qobuz (`lib/inspector.js:71`, `:97`) and HDRezka (`utils/httpInspector.js:142`,
  `:222`) call `proceed()` **in sync mode, where it is a no-op**. They work only
  because a function that falls off the end returns `undefined`, which
  `duk_get_boolean` coerces to `0` — the same verdict `return 0` gives. [INFER] Two
  independent authors adopted a call that does nothing, because it reads like the
  thing they wanted. anilibria's sync inspector (`lib/transport.js:22-34`) calls
  neither `proceed()` nor `return 0`; it falls off the end, which is accidentally
  the correct verdict.
  (Corrected 2026-08-10: this bullet read "three independent authors" and counted
  anilibria among them. Checked against the tree this survey actually read
  (`3802256`, 2026-08-05): `lib/api.js:32-44` sets headers and a cookie and ends at
  `}, false);` — no `proceed`, no `return`. The claim was false on the day it was
  written, and the citation beside it was the disproof.)

**Design vs. workaround: the author's is the design.** `return 0` in sync mode is
what the C reads. `proceed()` is the async handshake. The community collapsed the
two into one habit.

### 2.3 The 401-driven credential flow

[READ] `api.js:12-154` registers one async inspector on the API host and puts the
*entire* OAuth device flow inside it, gated on `ctrl.authFailed` (`api.js:18`).
Nothing in the plugin ever asks the user to log in; the first request that comes
back 401 raises the popup, and the request that triggered it is resumed with
`ctrl.proceed()` (`api.js:134`) rather than re-issued.

[CORE] `authFailed` and async mode arrived in the same commit, `ed878c718`
(2016-04-28) — the feature exists to make exactly this shape possible.

**The community copied the popup — and, in the one case measured, the mechanism
with it.** [READ] `movian-plugin-trakt/src/auth.js:9-133` is a near-verbatim
descendant of
`api.js:74-153` — same `credentials.apiauth` / `credentials.refresh_token` names,
same `interval += 1000` slow-down (`auth.js:95` vs `api.js:115`), same
`prop.setParent(message, prop.global.popups)` (`auth.js:44` vs `api.js:86`), and
the same three comments *verbatim*, including "This will make the subscription
destroy itself when the popup is destroyed. Without this we will retain references
to captured variables indefinitely" (`auth.js:128-131` vs `api.js:149-152`).
`movian-plugin-trakt/trakt.js:41` is byte-identical to `api.js:3`.

> **Retracted 2026-08-10.** This paragraph asserted "[MEASURED] zero
> `httpInspectorCreate` calls" in trakt and built the section's conclusion on it.
> The measurement was wrong and the conclusion it carried was the inverse of the
> truth. Both are replaced below. The claim is what a `[MEASURED]` tag is supposed
> to make impossible, and it survived to a fifth review; see the note at the end of
> this section.

[MEASURED] trakt has **one** inspector, `src/api.js:11-43`, and it is the same
shape as youtube's: `io.httpInspectorCreate('https://api.trakt.tv/.*', ..., true)`
— async mode (`:43`), skipping `/oauth/` via `ctrl.ignore()` (`:13-16`) to avoid a
loop, attaching `Authorization` when a token exists (`:18-23`), and on
`ctrl.authFailed` clearing the token (`:26`), trying `auth.refreshToken()` (`:28-35`)
and falling back to the full device-code login (`:38-42`), resuming with
`ctrl.proceed()` rather than re-issuing. The one `auth.login()` outside the inspector is `trakt.js:59`, the
callback of a `settings.createAction("login", ...)` button — a user-initiated
re-login for switching accounts, not an eager startup login.

**youtube functioned as the missing documentation, and the one plugin that
demonstrably read it copied both halves** — the popup *and* the lazy 401-triggered
inspector. [INFER] That is a weaker argument for a written canon than the inverse
would have been, and it should be stated as the weaker one: the corpus shows the
architecture travelling when a close reader copies a close neighbour, and says
nothing about what reaches everyone else. The seven plugins with no descent from
youtube are the population a canon is actually for.

**What this cost.** [INFER] The false measurement propagated into the skill
(`[4/9]` inspector count, "youtube is the only plugin that gets this right",
"dropped the mechanism, calling `login()` eagerly instead") and survived four
reviews before a fifth reader checked the source. A `[MEASURED]` tag is a claim
that a command was run; this one was not, or was run against the wrong tree.
Treat an unreproduced `[MEASURED]` as `[INFER]`.

### 2.4 `Duktape.modSearch` wrapping to host an unmodified npm package

[READ] `youtube.js:28-38` wraps the core's module loader so that bare specifiers
`html-entities`, `path` and `sax` resolve into `./support/`. **Unique in the
corpus** — [MEASURED] two hits, both in `youtube.js`.

The point is what it buys: `ytdl-core/` is dropped in essentially unmodified and
keeps its Node-shaped requires — `require('http')`, `require('https')`,
`require('url')` (`ytdl-core/lib/request.js:1-3`), `require('querystring')`
(`ytdl-core/lib/util.js:1`), `require('fs')` (`ytdl-core/lib/sig.js:1`). [CORE]
`res/ecmascript/modules/` ships `http.js`, `https.js`, `url.js`,
`querystring.js`, `fs.js` at top level precisely so that works. The three modules
the core *doesn't* ship get four-to-sixteen-line stubs in `support/` — including
`support/sax.js:1` "*Dummy SAX parser that never parses anything*" and
`support/jstream.js:1-3`, which returns the literal `5`.

**Design.** The intended way to consume an npm library is: vendor it, let the core's
Node shims carry it, and stub the rest — not rewrite it. That the stubs are jokes
(`support/path.js` is an empty file) is the demonstration that the shims only need
to satisfy the load, not the semantics.

Not era-contingent. [MEASURED] Nothing has removed the Node shims; they are in the
current core tree.

### 2.5 `args` as an array of objects

[READ] `api.js:171` `args: [{key: KEY}, params || {}]`. **The only site in the
corpus.** [CORE] `res/ecmascript/modules/movian/http.js:77-88` exists solely to
support it: "*If ctrl.args is an array we assume it's an array of objects so we
merge all those objects into one*". A shipped, documented core feature with exactly
one user, its author.

### 2.6 Reading the core's global property tree for region

[READ] `youtube.js:59-64` subscribes to `prop.global.location.cc` and re-reads
`REGION` whenever the core learns it. [CORE] `src/main.c:261` is where the core
sets it. **No other plugin reads it** — [MEASURED] the community's `prop.global`
traffic is `prop.global.navigators` (HDRezka `utils/resume/navigation.js:13`,
m7-jellyfin `src/navigator.js:10`, anilibria `lib/resume.js:116`) and
`prop.global.i18n` (m7-jellyfin `src/i18n.js:13`).

[INFER] The asymmetry is the point: the author reads the global tree for *facts the
core knows*; the community reaches into it to *drive navigation from outside a
page* — an escape hatch youtube never needs, because everything it does happens
inside a route.

### 2.7 `subtype` as a Material icon name

[READ] `youtube.js:234` `.root.subtype = 'subscriptions'`; `browse.js:211`
`'thumb_up'`; `browse.js:222` `'thumb_down'`; `browse.js:244` `'tv'`.
**The only plugin that sets `subtype`.** [CORE]
`glwskins/flat/items/list/default.view:19-20` resolves it as
`"ic_" + $self.subtype + "_48px"`, and all four SVGs exist:
`glwskins/flat/icons/ic_subscriptions_48px.svg`, `ic_thumb_up_48px.svg`,
`ic_thumb_down_48px.svg`, `ic_tv_48px.svg` (82 icons in that directory).

Nobody else discovered that a list item can carry an icon by name. This is a
canon-shaped fact that would otherwise never be written down.

---

## 3. What the author's plugin declines that everyone else reaches for

### 3.1 No global settings — at all

[MEASURED] youtube requires no settings module and calls no `Settings.*`. It is
**the only plugin of the nine with no user-visible settings page**. soap4.me
(`src/index.js:416-425`), HDRezka, trakt, m7-jellyfin, anilibria, qobuz, tmdb and
dailymotion all build one.

What it uses instead is *per-page* options: `browse.js:319` and `browse.js:332`
call `page.options.createMultiOpt(...)` for sort order and duration filter.
[CORE] `res/ecmascript/modules/movian/page.js:197-199` backs `page.options` with
`settings.kvstoreSettings(this.model.options, this.root.url, 'plugin')` — keyed on
**the page's URL**, so the choice persists for that search and not globally.

**The design reading: preferences belong to the page that uses them.** Not era —
the settings module predates the plugin by eighteen months (§1). HDRezka
(`pages/catalog.js:187-211`), m7-jellyfin (`src/view.js:535-579`) and tmdb
(`tmdb.js:1488-1523`) independently found `page.options` too, so the idiom
survives; what is unique is declining the *global* page entirely.

Caveat: youtube has genuinely little to configure. [INFER] The claim "settings
should be page-local" is weakly supported; the claim "a plugin does not need a
settings page to be complete" is strongly supported.

### 3.2 No `page.Searcher`

[MEASURED] youtube registers **no** searcher. [READ] soap4.me
(`src/index.js:414`), anilibria (`anilibria.js:79`), qobuz (`qobuz.js:411`) and
dailymotion (`src/ts/dailymotion.ts:88`, `:92`) all do. youtube instead puts a
`'search'`-typed item on its own landing page (`youtube.js:224-226`) pointing at
`youtube:search:`, with the query captured by the route regexp at `youtube.js:117`.

`Searcher` existed since 2014 (§1), so this is intent, not era. [INFER] The reading
is that the global search bar is for *aggregated* search across services, and a
service whose search needs its own order/duration options (`browse.js:319-343`)
does not belong there. **Reported as inference: I found no source comment or core
behaviour that states this**, and the four plugins that do register one are not
obviously wrong.

### 3.3 No `getAuthCredentials`

[READ] soap4.me `src/index.js:377` uses `Popup.getAuthCredentials(...)` — the core's
built-in username/password dialog, in the API since 2010 (§1). youtube builds its
popup by hand out of props: `prop.createRoot()` (`api.js:74`),
`prop.setRichStr` (`api.js:76`), `prop.setParent(popup, prop.global.popups)`
(`api.js:86`), `prop.subscribe(popup.eventSink, …)` (`api.js:142`).

**This is not a rejection of the helper; it is a case the helper cannot express.**
Google's device flow has no password field — it shows a URL and a code and polls.
`api.js:73` says so: "*We do this manually using properties because we want to wait
for event asyncronously*". The intent claim here is narrow and safe: **when the
built-in popup does not fit, the prop tree is the documented fallback, and the
`autoDestroy: true` subscription option (`api.js:152`, [CORE]
`res/ecmascript/modules/movian/page.js:66`, `:140`, `:234`, `:312`, `:371`) is what
keeps it from leaking.** The four-line comment at `api.js:149-152` explaining why
is the only such explanation anywhere in the corpus, and trakt copied it verbatim
(§2.3).

### 3.4 No `Plugin.manifest`

[MEASURED] youtube never reads `Plugin.manifest`; it hardcodes `"Youtube"` at
`youtube.js:94` and `PREFIX = "youtube"` at `youtube.js:42`, both duplicating
`plugin.json`. soap4.me (`src/index.js:10-19`), trakt (`trakt.js:48`
`plugin_info.title`), anilibria (`anilibria.js:25` `plugin.title`), HDRezka and
m7-jellyfin all read it.

**Here the community is right and the author is not.** [INFER] `Plugin.manifest`
is populated by [CORE] `src/ecmascript/ecmascript.c:900` for every plugin, so
nothing stopped him. Duplication in a 306-line file is cheap; the canon should not
adopt it. This is the clearest case in the whole reading where *intended* and
*good* diverge.

### 3.5 No transpile, no build, no tests

[MEASURED] youtube's 14 `.js` files are hand-written ES5 with no build step, no
`package.json`, no `use strict` and no tests. The map's convergence finding — four
of nine built a transpile step — describes what people did *without* guidance. The
author, who needed none, wrote ES5 directly. [INFER] This is weak evidence about
build tooling and strong evidence about *what the runtime is*: nothing in the
intended use requires more than ES5.1.

---

## 4. Where the idiom differs: design or workaround, one by one

| idiom | youtube | community | verdict |
|---|---|---|---|
| sync inspector verdict | `return 0` (`youtube.js:50`) | `proceed()` (no-op) | **youtube = design** ([CORE] `es_io.c:796-801`) |
| page-level image | `metadata.icon` (`youtube.js:109`, `:127`, `:222`) | `metadata.logo` (soap4.me `:156`, tmdb `:1504`, HDRezka `pages/player.js:50`, anilibria `lib/ui.js:46`) | **youtube = design** for what RENDERS; `logo` is not inert — see the correction in §6.1 |
| HTTP cache | `caching: true` (`api.js:174`) | `cacheTime: N` — HDRezka 13×, anilibria 3×. **Corrected 2026-08-09: m7-jellyfin was listed here at 3× and passes the flag ZERO times at runtime** — all its hits are hand-written `.d.ts` declarations, per [#21's survey](https://github.com/Buksa/movian-plugin-sdk/issues/21) | **both work, with different guarantees** — [CORE] `es_io.c:313-314`; `cacheTime` implies `caching` and additionally survives the header veto at `:414-415` |
| pagination | `asyncPaginator` + explicit `page.haveMore()` (`browse.js:270`, `:275`, `:308`) | **`asyncPaginator` too** — m7-jellyfin, dailymotion, HDRezka, trakt, anilibria; only **qobuz and tmdb** use the synchronous `paginator` | **not a divergence at all.** Corrected 2026-08-09: this row originally listed m7, dailymotion and HDRezka as `paginator` users, contradicting [#22's survey](https://github.com/Buksa/movian-plugin-sdk/issues/22), which measures 6/9 on `asyncPaginator`. The author's idiom is the majority one. [CORE] `page.js:208-225` — `asyncPaginator` short-circuits and the plugin owns `haveMore`; `paginator`'s return value sets it |
| module load timing | `require()` inside route handlers, 18 sites | top-of-file (soap4.me, tmdb, dailymotion: 0 deferred) | **youtube = design, and it says why**: `youtube.js:8-9` "*keep the main youtube.js file small for faster loading on slower devices*". HDRezka (63) and trakt (7) converged on it independently |
| requiring `native/*` | does it, and flags it: `youtube.js:45`, `api.js:4` `// XXX: Bad to require('native/')` | anilibria `lib/api.js:30` does it with a comment explaining there is no wrapper; trakt, m7, qobuz, HDRezka all do it | **workaround, self-declared.** The author calls his own line bad. Any canon rule against `native/*` can cite the author against himself |
| entry-file scope | relies on it: `PREFIX`/`REGION` are `var` at `youtube.js:41-42` and read from `browse.js:85`, `:289` | modules pass values explicitly | **era-ambiguous, see §7** |

On the last row's mechanism, so the canon does not have to guess: [CORE]
`src/ecmascript/ecmascript.c:839` compiles the entry with `duk_pcompile(ctx, 0)` —
**program code**, so top-level `var` in the entry file becomes a global property.
`require()`d files go through Duktape's CommonJS wrapper and are function-scoped.
That is why `browse.js` can read `PREFIX` without importing it, and it is a real
asymmetry the canon must state either way.

---

## 5. soap4.me: the outsider's bracket

Read against youtube, soap4.me diverges on one axis above all others: **it is
entirely synchronous.** [MEASURED] zero callback-form `http.request` calls; every
route handler blocks (`src/index.js:85-89`, `:105-109`, `:189-193`, `:288-299`).
youtube is entirely asynchronous — `api.js:178` is a three-argument
`http.request(URL, opts, cb)`, and every page fills in from a callback.

[CORE] `res/ecmascript/modules/movian/http.js:93-104` supports both by design, so
neither is wrong. But the consequences differ:

- soap4.me hand-rolls its own cache in a plain object (`src/index.js:81`,
  `:93`, `:113`) because a synchronous fetch has nowhere to put a cache policy.
  youtube sets `caching: true` and lets the core's HTTP cache do it (`api.js:174`).
- soap4.me has no pagination at all — every page renders its full result set.
  youtube paginates every list (`browse.js:261-275`).
- soap4.me cannot show progressive loading; `page.loading` flips true then false
  around a blocking call (`src/index.js:152`, `:179`).

**What the outsider got right that the author did not:** reading the manifest as
the single source of identity (`src/index.js:10-19`), and keeping the manifest itself in
`package.json` under a `movian` key, generating `plugin.json` from it at build
time (`movian-soap4.me/package.json`, `gulpfile.babel.js`). Its i18n table lives
there too. That is a better idea than anything in youtube.

**Correction to my own first draft, and to the map:** this is *not* unique.
[READ] `m7-jellyfin/package.json` carries the same `movian` key and commits no
`plugin.json` either — as
[#20](https://github.com/Buksa/movian-plugin-sdk/issues/20) established
independently. Two of the three build-using plugins converged on it with no
contact. That strengthens the recommendation rather than weakening it.

**What first contact cost him**, both citable:
- `src/index.js:380` redirects to `routes.LOGIN2`, which does not exist in the
  `routes` object (`src/index.js:54-62`). `page.redirect(undefined)` on the
  auth-rejected path.
- `page.metadata.logo` (`:156`, `:210`, `:246`) is not read by any skin, but it is not inert — see the correction in §6.1.

Together the two plugins bracket the range exactly as the ticket predicted: the
author reaches for asynchrony, the core's cache, pagination, the prop tree and the
URL space; the outsider reaches for structure, a build, and a single source of
truth — and guesses wrong about the property names, because there was nothing to
read.

---

## 6. Contradictions, reported not smoothed

### 6.1 Two properties the corpus writes that the core never reads

- **`page.metadata.logo`** — **CORRECTED 2026-08-06, this claim was wrong.**
  It has **zero** occurrences in `glwskins/`, which is true and is why nothing
  renders from it. But it is read in `src/`: `src/navigator.c:706-712` subscribes to
  `page/model/metadata/logo` and routes it to `nav_page_icon_set` — the icon a
  **bookmark** carries. The block sits under `#if ENABLE_BOOKMARKS`
  (`navigator.c:685`), and `build.debug/config.h:21` defines `ENABLE_BOOKMARKS 1`,
  so it is compiled and live.

  The core's own naming is what hides this: the subscription is `np_icon_sub` and
  the callback `nav_page_icon_set`, while the property they watch is `logo`.

  So `icon` and `logo` are two consumers for two purposes, not one real and one
  dead. The original claim came from grepping `.c` and `.view` for a rendering
  consumer and concluding absence — without checking conditional compilation. The
  same failure mode this project logged twice today under
  [[typecheck-is-not-execution]]: absence found by one search is not absence.
  `metadata.icon` is real (`glwskins/flat/theme.view:167`,
  `glwskins/flat/items/list/audio.view:38-39`,
  `glwskins/flat/items/rect/video.view:17`). Four plugins write `logo`; the author
  writes `icon`.
- **`page.metadata.showTitleAndIcon`** — [READ] `youtube.js:177`. [CORE] **zero**
  occurrences anywhere in the core checkout. **The author's own plugin sets a
  property nothing consumes.** Whether it was ever consumed and later removed, I
  did not establish.

### 6.2 The like/dislike buttons operate on the wrong item

[READ] `browse.js:193-223`. The loop builds `aux = {vid: vid, item: item}`
(`:197-200`) — evidently to escape `var` capture — but the success callbacks at
`:205-206` and `:216-217` call `item.destroyOption(...)` on the bare `item`, not
`this.item`. `item` is `var`-declared at `:195` inside a `for…in`, so it holds the
**last** video's item by the time any callback fires. `aux.item` is stored and
never read. Rating the third video removes the buttons from the last one.

This is in the feature whose core-side support landed the same day (§0).

### 6.3 A dead condition in the My Channel route

[READ] `youtube.js:189-196`. `for(a in relatedLists)` declares `a` with no `var` —
an implicit global. `:190` reads `var type = relatedLists[a]`, `:191` reads
`var playlistid = …relatedPlaylists[type]`, and `:192` guards with `if(type)` —
which is always truthy, since `type` comes from the literal array at `:186`. The
guard was meant for `playlistid`. Absent related playlists push `undefined` into
`idlist` and create an item at `youtube:playlist:undefined`.

`api.js:74` has the same class of slip: `popup = prop.createRoot()` with no `var`.

### 6.4 Vendored dead code

[READ] `ytdl-core/lib/index.js:1` requires `stream`, which the core does not ship
([CORE] `res/ecmascript/modules/` has no `stream.js`). It never fails because
nothing loads it — `youtube.js:264` requires `./ytdl-core/lib/info` directly,
bypassing the package entry. [INFER] The vendoring pattern of §2.4 tolerates
partially-unloadable packages; the canon should say the shims must cover the
*reached* subtree, not the package.

---

## 7. Claims I could not separate — reported as unseparable

1. **Entry-file globals.** `PREFIX`/`REGION` crossing from `youtube.js` into
   `browse.js` works because of the program-vs-module compile asymmetry (§4). I
   cannot tell whether the author regarded that as an interface or merely used it.
   It is not era — the asymmetry still holds in the current core — but "design"
   and "convenience nobody thought about" are indistinguishable from the source.
   No comment addresses it.
2. **Declining `page.Searcher` (§3.2).** Intent as to *timing* (the API existed),
   unseparable as to *reason*. My aggregated-search reading is inference with no
   corroborating source.
3. **`showTitleAndIcon` (§6.1).** Cannot distinguish "written against a skin
   property since removed" from "written speculatively". Would need skin history I
   did not walk.
4. **Whether hardcoding identity (§3.4) was a position or an oversight.** The
   plugin predates most manifest-reading plugins, and `Plugin.manifest` may have
   been added after 2016-05; I did not date it. Until dated, the "community is
   right" verdict stands on merit, not on the author's disagreement.
5. **No tests / no build (§3.5).** Cannot separate intent from 2016 practice.

---

## 8. What the canon can safely take from this

Ranked by strength of evidence.

1. **A plugin is a handler for a URL space.** Declare `control.uriprefixes` and
   route raw service URLs. Cite `plugin.json:14-22` + `youtube.js:301-306` +
   [CORE] `src/plugins.c:2211-2221`. Uncontested, unique, deliberate.
2. **HTTP inspectors have two protocols; do not mix them.** Sync → `return 0`.
   Async (third arg `true`) → `proceed()` / `fail()`. Cite `youtube.js:50`,
   `api.js:22/125/134/154`, [CORE] `es_io.c:635-645`, `:796-801`. Three community
   plugins get this wrong harmlessly today.
3. **Credentials belong on the 401, not on a login button.** Register an async
   inspector, gate on `ctrl.authFailed`, resume with `proceed()`. Cite
   `api.js:12-154`. Note that the one plugin that copied the popup dropped the
   mechanism.
4. **`page.metadata.icon` is what RENDERS; `logo` feeds bookmarks.** Cite [CORE]
   `theme.view:167` for the first and `navigator.c:706-712` for the second. The four
   plugins writing `logo` are not wrong — they are setting a different thing. Whether
   they MEANT to is a separate question the canon should ask.
5. **`subtype` is a Material icon name.** Cite `youtube.js:234`, `browse.js:211`,
   [CORE] `glwskins/flat/items/list/default.view:19-20` and the icon files.
6. **Options belong to the page, not to a global settings screen** — at least by
   default. Cite `browse.js:319-343` and [CORE] `page.js:197-199` (kvstore keyed
   on page URL).
7. **`require()` inside route handlers**, with the author's stated reason. Cite
   `youtube.js:8-9`.
8. **Vendor npm packages; let the core's Node shims carry them; stub the rest.**
   Cite `youtube.js:28-38`, `support/*.js`, [CORE] `res/ecmascript/modules/`.
9. **Read identity from `Plugin.manifest`** — taken from the *community*, against
   the author. Cite soap4.me `src/index.js:10-19`, trakt `trakt.js:48`.
10. **`require('native/*')` is a smell.** Cite the author flagging his own line:
    `youtube.js:45`, `api.js:4`.

And one methodological note for the canon itself: the youtube plugin propagated
into trakt comment-for-comment while its architecture did not travel at all
(§2.3). The corpus's convergence is not evidence of independent discovery
everywhere — some of it is copying. Any canon claim resting on "N plugins agree"
should first check whether the N share a lineage.
