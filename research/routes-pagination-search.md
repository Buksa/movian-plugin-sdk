# Routes, pagination, search, services and item metadata across the nine

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

Resolves [Buksa/movian-plugin-sdk#22](https://github.com/Buksa/movian-plugin-sdk/issues/22)
(part of map [#19](https://github.com/Buksa/movian-plugin-sdk/issues/19)).

**Method.** Every claim below is read out of source at a cited `file:line`. Core paths are
relative to `/home/uzver/movian-public-clean` (checkout of `Buksa/movian`, `movian6`);
plugin paths are relative to each plugin checkout under `/home/uzver`. Statements are
labelled **[M]** measured (read from the cited line) or **[I]** inferred (a conclusion
drawn from measured lines, stated separately so it can be falsified).

The two "teaching examples" named in the ticket are **not** in the core checkout. The core
has only `plugin_examples/async_page_load`; `02-intermediate/05-pagination` and
`02-intermediate/04-search-provider` live in a loose tree at `/home/uzver/plugin_examples/`
that is not tracked by the core repo. **[M]** `ls /home/uzver/movian-public-clean/plugin_examples`
returns `README async_page_load itemhook listx_cloner music settings subscriptions
videoscrobbling webpopupplugin` — neither `02-intermediate` nor `01-basics` is present.
Both loose examples are read below anyway, and both are **wrong against the core API**
(§5). This matters for map #19's "Relationship to the example corpus" fog: the exhibits
the canon would inherit are not currently correct.

---

## 0. Ground truth — what the core actually offers

### 0.1 `Route` — regex, priority, capture groups

**[M]** `res/ecmascript/modules/movian/page.js:384-406`:

```js
exports.Route = function(re, callback) {
  this.route = require('native/route').create(re, function(pageprop, sync, args) {
      pageprop = prop.makeProp(pageprop);
      args.unshift(new Page(pageprop, sync, false));
      callback.apply(null, args);
```

The callback receives `(Page, ...captureGroups)`. There is no options object, no named
parameters, and no query-string parsing — the only channel from URL to handler is
**positional regex capture groups**.

**[M]** `src/ecmascript/es_route.c:109-115` — a pattern not starting with `^` is
silently anchored: `s[0] = '^'` and the original is appended. Patterns are therefore
prefix-anchored but **not** end-anchored.

**[M]** `src/ecmascript/es_route.c:123-130` — registering a pattern string that already
exists throws `"Route %s already exist"`.

**[M]** `src/ecmascript/es_route.c:145`:

```c
er->er_prio = strcspn(str, "()[]*?+$") ?: INT32_MAX;
```

Priority is the byte offset of the first regex metacharacter; a pattern with **no**
metacharacters gets `INT32_MAX`. **[M]** `es_route.c:95-98` sorts descending
(`b->er_prio - a->er_prio`) and `es_route.c:147` inserts sorted. **[M]**
`es_route.c:189-199` (`ecmascript_openuri`) walks the list in order and takes the
**first** regex that matches.

**[I]** Consequences, all falsifiable by ordering experiment: (a) literal routes always
beat pattern routes regardless of registration order; (b) among pattern routes the one
with the **longer literal prefix** wins; (c) two patterns whose literal prefixes are the
same length tie, and the winner is decided by insertion order among equals, i.e. by
`require` order — this is a real hazard, see §1.3 (m7-jellyfin) and §1.8 (dailymotion).

**[M]** Only 8 capture slots exist: `hts_regmatch_t matches[8]` at `es_route.c:171`
and `es_route.c:191`. HDRezka's six-group `ROUTE_PATTERN` (§1.1) is the closest any
plugin comes to that ceiling.

### 0.2 `Searcher` — a global hook, not a page member

**[M]** `page.js:413-447`: `Searcher(title, icon, callback)` registers a
`native/hook` named `'searcher'`; on each global search the core creates a fresh root
prop, sets `root.metadata.title = title` / `root.metadata.icon = icon`, sets
`root.type = 'directory'`, parents it under the aggregated search model, wraps it in a
**flat** `Page` (`new Page(root, false, true)`), brackets the callback with
`prop.atomicAdd(loading, ±1)`, and calls `callback(page, query)`.

**[M]** Because the Page is constructed with `flat = true`, `page.js:196-200` skips
creating `this.options` — **a Searcher page has no `page.options`**. **[M]** `flat` also
makes `this.model = this.root` (`page.js:154`), so `page.metadata` on a searcher page is
the same node whose `title`/`icon` the core just set at `page.js:424-425`.

**[M]** `Page` has no `searchable` and no `onsearch` member: the full member list is
`page.js:239` `haveMore`, `:243` `findItemByProp`, `:252` `error`, `:258` `getItems`,
`:263` `appendItem`, `:299` `appendAction`, `:320` `appendPassiveItem`, `:333` `dump`,
`:337` `flush`, `:341` `redirect`, `:352` `onEvent`, plus the accessors defined at
`page.js:160-194` (`type`, `metadata`, `loading`, `source`, `entries`, `paginator`).

### 0.3 The third search mechanism: item type `'search'`

Not mentioned in the ticket, but used by four plugins. **[M]**
`glwskins/flat/pages/list.view:32-33` picks an item view by type:
`source: "skin://items/list/" + $self.type + ".view"`. **[M]**
`glwskins/flat/items/list/search.view:3` is just `SearchBar($self.url, $self.metadata.title);`.
**[M]** `glwskins/flat/theme.view:187-236` defines `SearchBar(URLPREFIX, TEXT, ICON)` as an
inline focusable text widget bound to `$view.searchQuery` with
`onEvent(enter, navOpen(URLPREFIX + $view.searchQuery), ...)` at `theme.view:227-230`.

**[M]** So `page.appendItem('<prefix>:search:', 'search', {title: ...})` renders an
in-page search box that, on Enter, navigates to `<prefix>:search:<query>` — which the
plugin then serves with an ordinary `Route`. A `rect` variant exists too
(`glwskins/flat/items/rect/search.view`).

### 0.4 Pagination — three distinct mechanisms, all in one subscription

**[M]** `page.js:202-235`: a single `prop.subscribe` on `model.nodes` handles the
`wantmorechilds` operation the UI raises when the cloner runs out of items:

```js
if(typeof this.asyncPaginator == 'function') { this.asyncPaginator(); return; }   // :208-211
if(typeof this.paginator == 'function') { have_more = !!this.paginator(); }        // :213-224
prop.haveMore(nodes, have_more);                                                   // :225
```

Therefore: **[M]** `asyncPaginator` short-circuits and returns before `haveMore` is
touched — the plugin owns `haveMore` entirely and must call `page.haveMore(...)` itself.
**[M]** `paginator` is synchronous: its **return value** is the "more?" flag, and the
core sets `haveMore` for you. **[M]** If both are set, `asyncPaginator` wins and
`paginator` is dead code. **[M]** Setting `.paginator` also implicitly calls
`this.haveMore(true)` via the accessor at `page.js:186-192`; setting `.asyncPaginator`
does not (it is a plain property).

**[M]** `page.js:217-223` swallows a paginator throw only when the page prop is already a
zombie; otherwise it rethrows.

### 0.5 Services and the home screen

**[M]** `res/ecmascript/modules/movian/service.js:27-32`:
`exports.create(title, url, type, enabled, icon)` calls `native/service.create` with the
id `"plugin:" + Plugin.id`.

**[M]** `src/service.c:227-268` (`service_create0`) creates a prop root carrying
`title`, `metadata.title` (linked to `title`), `icon`, `url`, `enabled`, `type`,
`status`, `origin`, and parents it under `all_services` (`service.c:267-268`).

**[M]** `src/service.c:103-124` — `$global.services.all` is the raw set;
`$global.services.enabled` is a `prop_nf` filter over it that **excludes** nodes whose
`node.enabled == 0`. **[M]** `service.c:126-136` builds `$global.services.stable` the
same way plus a user-defined reorder (`allSourcesOrder`).

**[I]** What makes a plugin appear on the home screen is therefore exactly two things:
calling `service.create(...)` at plugin load, and the `enabled` argument being truthy.
There is no separate "register on home" call. **[M]** `service.c:344-349` additionally
binds `enabled` to a persisted setting, so a user can switch a plugin off the home screen
without the plugin knowing.

### 0.6 Item metadata

**[M]** `page.js:263-297` — `appendItem(url, type, metadata)` assigns `root.metadata =
metadata` wholesale; the whole JS object is deep-copied into the prop tree by
`prop.makeProp`. There is no schema and no validation.

**[M]** When `type == 'video'`, `page.js:273-293` additionally parses a
`videoparams:` URL for `canonicalUrl` (or the first `sources[i].url`) and calls
`require('native/metadata').bindPlayInfo(root, metabind_url)` — i.e. watched-state and
resume position are bound automatically for video items, keyed on the canonical URL.

**[M]** Explicit binding is available as `Item.prototype.bindVideoMetadata`
(`page.js:21-26` → `native/metadata.videoMetadataBind`).

**[M]** The metadata key vocabulary the flat skin actually reads, by frequency across
`glwskins/flat/items/` + `glwskins/flat/pages/`: `title` (43), `icon` (22), `duration`
(10), `start`(9)/`events`(9)/`stop`(3) (EPG), `episode` (4), `year`, `tagline`, `rating`,
`glwview`, `description`, `backdrop(s)`, `artist`, `season`, `subtitle`, `synopsis`,
`track`. **[I]** Any other key a plugin sets is inert unless the plugin ships its own
`.view`.

---

## 1. Per plugin

### 1.1 HDRezka — `require('movian/x')`, swc build, 17 routes

- **Routes.** `routes/index.js:12` wraps every registration in an `init()` function
  called from the entry point; each is `new page.Route(PREFIX + ':<verb>', handler)` at
  `routes/index.js:13,17,22,28,34,40,46,51,94,102,106,110,114,122,152,165`.
- **Arguments.** Two idioms. (a) A single opaque capture that the handler decodes:
  `routes/index.js:22` `PREFIX + ':catalog:(.*)'` → `ui.decodePayload(payload)` at `:23`.
  (b) A **shared six-group pattern**, `ROUTE_PATTERN` (`utils/ui.js:8`, re-exported from
  `utils/codec.js`), reused across four routes so the handler signature is uniform:
  `routes/index.js:28,34,40,46` all read
  `function (p, type, id, tr, s, e, meta)` and call `ui.decode(type, id, tr, s, e, meta)`.
  **[I]** This is the only plugin that treats the URL as a **typed record** rather than
  an ad-hoc string, and it is the only one near the 8-group ceiling (§0.1).
- **Pagination.** `asyncPaginator`, hand-tuned. `pages/catalog.js:218` `page.asyncPaginator = loader`,
  with a load mutex (`:26,68-69`), a monotonic `loadToken` for cancellation (`:27,61,126`),
  a 15 s watchdog that releases the mutex if the fetch hangs (`:115-121`), and — the
  distinctive part — a **deliberate delay before exposing `haveMore(true)`**:
  `catalog.js:10-13` `FIRST_PAGE_PAGINATION_DELAY = 1200`, `CACHE_PAGINATION_DELAY = 50`,
  applied at `:33-55`. The comment at `:10-11` states the reason: GLW cloners request
  more children immediately when `haveMore(true)` is set while every card is active.
  **[I]** This is a workaround for a core/UI behaviour, discovered empirically; it is the
  single strongest piece of evidence that raw `asyncPaginator` is under-specified.
- **Search.** *Both* mechanisms. Global `new page.Searcher(PREFIX, 'search', ...)` at
  `routes/index.js:61`, which shows **only the first 3 hits** (`:73-83`) and then appends
  a "show all" item pointing at its own route (`:86-89`); and the own route
  `PREFIX + ':search:(.*)'` at `:51`, which reuses the catalog page.
  **[M] Divergence:** the Searcher's `icon` argument is the bare string `'search'`
  (`:61`), not a path; `page.js:425` assigns it straight to `root.metadata.icon`.
- **Service.** `service.js:77` `service.create(constants.TITLE, constants.PREFIX + ':start', 'video', true, constants.LOGO)`,
  inside an `init()` that also installs an HTTP inspector and the settings tree.
- **Metadata.** `pages/catalog.js:155-161` — `{title, description, icon}` plus an explicit
  `ui.bindMetadata(it, 'rezka:' + item.type + ':' + item.id)`. **[M]** `utils/ui.js:27-33`
  sets `item.root.canonical_url` and calls `require('native/metadata').bindPlayInfo`
  directly. **[I]** Because the item URL is `HDRezka:details:<payload>` and not a
  `videoparams:` URL, the automatic binding at `page.js:273-293` would not fire; HDRezka
  reimplements it against a stable synthetic canonical URL so watched-state survives
  payload changes.
- **Page shape.** `catalog.js:21-22` sets `page.type = 'raw'` with
  `page.metadata.glwview = Plugin.path + 'views/grid_video_switcher.view'` — it opts out
  of the stock directory renderer entirely.

### 1.2 trakt — `require('showtime/x')`, 40 routes, no Searcher

- **Routes.** 40 top-level `new page.Route(...)` calls in one file, `trakt.js:89-249`,
  each a one-line delegate into `src/view.js` (e.g. `trakt.js:89-91`).
- **Arguments.** Positional captures, up to four: `trakt.js:228`
  `PREFIX + ":show:(.*):season:(.*):episode:(.*):config:(.*)"`. Structured payloads are
  passed as a `config` capture that the view JSON-decodes.
- **Pagination.** `asyncPaginator`, **assigned twice**. `src/view.js:150`
  `if (!config.noPaginator) page.asyncPaginator = loader;` installs the initial loader;
  then inside the callback, `src/view.js:141-143` **replaces** it with the API's own
  next-page thunk `pagination.loadNextPage` and calls `page.haveMore(true)`. The thunk is
  manufactured in `src/api.js:107-125` out of Trakt's `x-pagination-*` response headers
  (`:111-113`) — `pagination.loadNextPage = Api.call.bind(api, uri, newOpts, callback)`
  at `:120`. **[I]** This is the cleanest "pagination cursor lives in the HTTP layer, page
  object just holds the current continuation" design in the corpus.
  A **non-paginating** mode also exists: `config.noPaginator` swaps the paginator for a
  literal "See more" directory item (`src/view.js:132-136`).
- **Search.** Own route only — `trakt.js:203` `PREFIX + ":search:(.*)"`. **[M]** Grep for
  `Searcher` across `movian-plugin-trakt/**/*.js` (excluding `node_modules`) returns
  nothing. The entry point is an item of type `'search'`: `src/view.js:260`
  `page.appendItem(PREFIX + ":search:", 'search', {...})` (§0.3).
- **Service.** `trakt.js:48-49` `service.create(plugin_info.title, PREFIX + ":start", "video", true, plugin.getLogoPath())`.
  **[M]** `plugin_info` comes from `plugin.getDescriptor()` (`trakt.js:45`), i.e. the
  manifest — the same idiom map #19 attributed only to soap4.me.
- **Metadata.** Minimal: `src/view.js:32-35` and `:47-50` append `{title, icon}` only,
  with `icon` produced by `utils.toImageSet(...)` (Movian's `imageset:` multi-resolution
  JSON form). Detail pages instead set `page.metadata.glwview` and ship their own views
  (`src/view.js:526,753,1021,1224`).

### 1.3 m7-jellyfin — `require('movian/x')`, ES2015 classes, swc, **declarative route table**

- **Routes.** The only **table-driven** registration in the corpus. `src/view.js:14-56`
  is a `this.routes = [{path, view}, ...]` array; `src/view.js:76-80`:

  ```js
  routing() {
    this.routes.forEach((route) => {
      new page.Route(`${this.prefix}:${route.path}`, route.view.bind(this));
    });
  }
  ```

  **[M]** `.bind(this)` is what makes class methods usable as route handlers — the
  Page-first callback contract (§0.1) gives the handler no receiver.
- **[M] Hazard.** `src/view.js:32-39` registers `series:(.*)` **before**
  `series:(.*):season:(.*)`. Both patterns' literal prefixes end at the same `(`
  (`jellyfin:series:`), so `strcspn` (§0.1, `es_route.c:145`) gives them **equal
  priority** and the tie is broken by insertion order. **[I]** Since `(.*)` is greedy and
  unanchored at the end, `jellyfin:series:5:season:2` is matchable by the earlier,
  shorter pattern; whether it actually wins depends on `LIST_INSERT_SORTED` behaviour for
  equal keys, which I did not execute. Flagged as an ordering hazard the canon should
  rule on, not as a confirmed bug.
- **Pagination.** `asyncPaginator` with an offset/total cursor. `src/view.js:254`
  `page.asyncPaginator = browse.bind(this)`; the loader at `:241-243` computes
  `hasMore = offset < totalEntries`, sets `page.entries = totalEntries` and calls
  `page.haveMore(hasMore)`. **[M]** Each batch is wrapped in `setTimeout(..., 125)`
  at `src/view.js:225` — **[I]** the same class of workaround as HDRezka's 1200 ms delay
  (§1.1), arrived at independently.
  Non-paginated pages call `page.haveMore(false)` explicitly (`src/view.js:162`).
- **Search.** Own route `search:(.*)` (`src/view.js:25-27`), reached from an item of type
  `'search'`: `src/view.js:115` `page.appendItem(\`${this.prefix}:search:\`, 'search', ...)`.
  No `Searcher`. **[M]** Grep for `Searcher` under `m7-jellyfin/src` and `bin` returns nothing.
- **Service.** `src/jellyfin.js:47` `service.create(this.title, \`${this.id}:start\`, 'video', true, this.icon)`
  inside the plugin class's `init()`; `title`/`id`/`icon` are getters over
  `JSON.parse(Plugin.manifest)` (`src/jellyfin.js:16-44,83`).
- **Metadata.** `src/api.js:349-380+` — `parseItem(item)` returns a metadata object built
  per Jellyfin item type, with per-type image geometry (Episode 600×600, Audio/MusicAlbum
  175×175, Movie/default 315×177). `src/view.js:155` (favourites) and `:232`
  (library) then do `page.appendItem(path, type, mediaItem)` where `{path, type}` comes
  from `getMediaPath(item)` — **[I]** a two-function split (URL derivation vs metadata
  derivation) that no other plugin has.

### 1.4 anilibria — `require('movian/x')`, plain ES5, extracted pagination library

- **Routes.** Four: `anilibria.js:153,158,163,180`. Only one takes an argument:
  `PREFIX + ':release:(.*)'` → `function (page, id)` at `:180`.
- **Pagination.** The **only plugin with pagination factored into a reusable module**.
  `lib/pagination.js:19-111` is a callback-driven state machine
  (`loadPage`, `onLoadStart`, `onLoadEnd`, `onItems`, `onError`, `onHaveMore`) with an
  injectable `scheduler` (`:26-29`) so it is unit-testable (`tests/pagination.test.js`).
  Wired at `anilibria.js:108-148`; `anilibria.js:147` `page.asyncPaginator = pager.load`.
  **[M]** It reimplements HDRezka's timing workaround verbatim —
  `lib/pagination.js:37-38` `firstPageDelay = 1200`, `cacheDelay = 50`,
  `loadTimeout = 15000`, and the same `paginationDelay` shape at `:47-51` as
  `pages/catalog.js:33-37`. It adds one thing HDRezka lacks: **prefetch on cache hit**,
  `lib/pagination.js:102-104` (`maxPrefetchPage`, set to 1 at `anilibria.js:109`).
  **[I]** Same author as HDRezka; this is HDRezka's loop extracted and generalised, not
  independent convergence. Weigh it as one data point, not two.
- **Search.** Global Searcher only — `anilibria.js:79`. **[M] Divergence:** it is called
  **without `new`**: `page.Searcher(plugin.title, LOGO, function (page, query) {...})`.
  Compare HDRezka `routes/index.js:61`, qobuz `qobuz.js:411`, dailymotion
  `dailymotion.ts:88,92`, soap4.me `src/index.js:414`, all of which use `new`.
  **[I]** `page.js:413-414` only assigns `this.searcher = ...register(...)`; the
  registration is a side effect of `register`, so under Duktape's non-strict `this ===
  globalThis` the hook still installs and the handle is rooted on the global object. It
  works by accident and loses the `destroy()` handle (`page.js:451-453`).
  There is **no** `:search:` route (grep for `search` in `anilibria.js` hits only
  `api.search` at `:91`), so anilibria's search results are reachable **only** through the
  global search page.
- **Service.** `anilibria.js:25` `service.create(plugin.title, PREFIX + ':start', 'video', true, LOGO)`,
  where `plugin = JSON.parse(Plugin.manifest)` at `:16` — the soap4.me idiom again.
- **Metadata.** Fully deferred: `lib/ui.js:34` etc. is uniformly
  `page.appendItem(item.url, item.type, item.metadata)`; the `{url, type, metadata}`
  triple is produced by `lib/formatters.js` (`fmt.catalog(...)` at `anilibria.js:118`).
  **[I]** The only plugin that treats "a page item" as a data type produced by a pure
  formatter and consumed by a dumb renderer.

### 1.5 youtube — andoma's own, `require('showtime/x')`

- **Routes.** `youtube.js:100-306`, 20 registrations. Notably **six literal URL routes**
  for `youtube.com` / `youtu.be` watch and playlist URLs (`youtube.js:156-159,301-306`),
  paired with a `control.uriprefixes` block in `plugin.json`. **[I]** This is the only
  evidence in the corpus of the intended way a plugin claims *foreign* URLs, and it
  depends on the `strcspn` priority rule (§0.1) to outrank nothing else — these patterns
  have long literal prefixes and win easily.
- **Arguments.** Positional, one capture each. Route callbacks are sometimes named
  functions shared across patterns (`videoPage`, `playlistPage` at `:155-159`, `:298-306`)
  rather than inline closures.
- **Pagination.** `asyncPaginator`, driven by an opaque **API continuation token**.
  `browse.js:275` and `:346` `page.asyncPaginator = loader`; the loader stores
  `query.pageToken = result.nextPageToken` and calls `page.haveMore(!!query.pageToken)`
  (`browse.js:270-271`, `:308-309`). The loader is installed *after* the first call
  (`browse.js:274-275`) — **[I]** deliberate, so the first load is not treated as
  pagination.
  Filter changes reload rather than paginate: `browse.js:313-316` `reload()` does
  `delete query.pageToken; page.flush(); loader();`, and the sidebar options guard on
  `if(page.asyncPaginator)` (`:327,340`) so the option callbacks' initial fire is ignored.
- **Search.** **No `Searcher` at all.** The author's own plugin uses the item type
  `'search'` (§0.3): `youtube.js:224` `page.appendItem(PREFIX + ":search:", 'search', {title: 'Search Youtube'})`
  plus the route `PREFIX + ":search:(.*)"` at `:117`. **[I]** Strong evidence that a
  per-plugin search box is the *intended* primary form and the global `Searcher` is the
  secondary, opt-in aggregation.
- **Service.** `youtube.js:94-95`, with the comment `// Create the service (ie, icon on
  home screen)` — the author's own one-line statement of §0.5.
- **Metadata.** The richest in the corpus and the only one that **mutates metadata after
  append**: `browse.js:233-239` reaches into `items[itemid].root.metadata` and sets
  `duration`, `description`, `viewCount`, `likeCount`, `dislikeCount` from a *second*
  API call, then attaches a context-menu action with `addOptURL` (`:242-244`).
  Page-level icons use the `imageset:` form: `youtube.js:88` `page.metadata.icon =
  'imageset:' + JSON.stringify(item.snippet.thumbnails)`.
  It is also the only plugin that sets `root.subtype` on an item (`youtube.js:234`).

### 1.6 qobuz — `require('movian/x')`, the only **synchronous `paginator`**

- **Routes.** Five, `qobuz.js:288,321,345,369,399`; single positional capture each.
- **Pagination.** The **only** use of the synchronous `page.paginator` contract in the
  live corpus. `qobuz.js:243-265` `makePaginator(fetch)` returns a closure over
  `offset`/`total`/`PAGE_SIZE = 50` that **returns a boolean**; `qobuz.js:272-282`
  `installPaginator` loads the first block eagerly and then either sets
  `pageObj.paginator = loadMore` (`:279`) or `pageObj.haveMore(false)` (`:281`).
  **[M]** The code comments cite the core: `qobuz.js:269-270` — *"Assigning `paginator`
  also flags that more items may exist — see res/ecmascript/modules/movian/page.js:184"*.
  That is the accessor at `page.js:186-192` (§0.4). **[M]** It also guards the pathological
  case the core does not: an endpoint that keeps returning an empty page
  (`qobuz.js:260-262`).
  **[I]** Synchronous `paginator` is viable here only because qobuz's HTTP calls are
  blocking; it would deadlock a callback-style API client.
- **Search.** *Both*: `new page.Searcher('Qobuz', LOGO, ...)` at `qobuz.js:411` **and** an
  own route `PREFIX + ':search:(.*)'` at `:369`. **[M]** The Searcher body is wrapped in
  `try/catch` with the comment *"A failing searcher must not break the aggregated search
  page"* (`qobuz.js:427-430`) — **[I]** a correct observation about the shared hook, since
  `page.js:438-445` only suppresses the throw when the page prop is a zombie.
- **Service.** `qobuz.js:432` `service.create('Qobuz', PREFIX + ':start', 'music', true, LOGO)`
  — the only non-`'video'` service `type` in the corpus.
- **Metadata.** `qobuz.js:213-218` (`appendAlbum`) and `:220-234` (`appendTrack`); tracks
  carry the audio vocabulary `{title, artist, album, icon, duration}`.

### 1.7 tmdb — apiversion 1, global `plugin` object, 2858 lines, no `require`

- **[M] It is v1 by omission.** `movian-plugin-tmdb/plugin.json` has no `apiversion`
  field; `src/plugins.c:688` defaults it to 1, and `src/ecmascript/ecmascript.c:913-919`
  loads `res/ecmascript/legacy/api-v1.js` before the plugin when `version == 1`.
- **[M] The v1 surface is a thin shim over the same API.** `legacy/api-v1.js:104-121`:
  `createService` → `movian/service.create`, `addURI` → `new page.Route(re, callback)`,
  `addSearcher` → `new page.Searcher(...)`. **[I]** So v1 vs v2 is a *spelling* difference
  only; nothing in this survey behaves differently under v1.
- **Routes.** 24 `plugin.addURI(...)` calls, `tmdb.js:238` through `:2857`. Arguments are
  positional captures exactly as in v2 (`tmdb.js:307`
  `PREFIX + ":search:movies:(.*):(.*)"` → `function (page, query, year)`).
- **Pagination.** `page.paginator` — **but broken**. `tmdb.js:259-301`:

  ```js
  function paginator() {
      while(true) {                      // :263
          var data = loader(offset);     // :264
          ...append items...
          if(offset == total_pages) break;   // :292-293
          offset++;                          // :295
      }
      return offset < page.entries;      // :300
  }
  paginator();                           // :303
  page.paginator = paginator;            // :304
  ```

  **[M]** The first call at `:303` therefore drains **every** page of the result set
  synchronously before returning; the `page.paginator` assignment at `:304` is
  near-meaningless. **[M]** The return at `:300` compares a *page index* (`offset`)
  against an *item count* (`page.entries`, set to `data.total_results` at `:266`) — a type
  confusion. **[M]** A second copy at `tmdb.js:2436-2466` has the same `while(true)` and
  the `page.paginator = paginator` line **commented out** (`:2466`).
  **[I]** Whoever wrote the second copy noticed something was wrong and disabled the
  symptom rather than the loop. This is the clearest example of an author reaching the
  right API with the wrong model of it.
- **Search.** Own routes only (`tmdb.js:307` movies-by-query, `:520` `PREFIX + ":search"`).
  **[M]** No `addSearcher` call anywhere in `tmdb.js`.
- **Service.** `tmdb.js:24-25` `plugin.createService(plugin_info.title, PREFIX + ":start", "video", true, plugin.path + "logo.png")`
  — same five arguments, v1 spelling.
- **Metadata.** `tmdb.js:276-283` — `{title, icon: "tmdb:image:poster:" + it.poster_path}`
  plus optional `background: "tmdb:image:backdrop:" + ...`. **[I]** The `tmdb:image:...`
  URLs are served by tmdb's own faprovider routes, i.e. metadata values may be *plugin
  URLs*, not just http URLs — a mechanism no other plugin uses. It also sets
  `page.contents = "movies"` and `page.metadata.glwview` from *inside the pagination
  loop* (`:296-297`), which is why they are set repeatedly.

### 1.8 dailymotion — TypeScript → JS, `import x = require(...)`

- **Routes.** `src/ts/dailymotion.ts:45-86`, 13 registrations. **[M]** Two are passed a
  bare function reference rather than a closure (`:85-86` `new page.Route(..., view.video)`),
  which works because of the Page-first contract (§0.1).
- **[M] Ordering hazard, same class as §1.3.** `:53` `":channel:(.*)"` is registered
  before `:61` `":channel:(.*):videos"`, and `:77` `":user:(.*):(.*)"` before `:81`
  `":user:(.*):(.*):videos"`; the literal prefixes are equal length, so `es_route.c:145`
  gives equal priority.
- **Arguments.** Positional; `:69-75` shows the plugin doing its own
  `decodeURIComponent(query)` on the capture — **[M]** the core does not decode captures.
  Note the asymmetry: the `Searcher` path at `:88-93` passes `query` **undecoded** to the
  same view functions.
- **Pagination.** `asyncPaginator`, reassigned per page like trakt (same author).
  `src/ts/support/view.ts:142` `if (!config.noPaginator) page.asyncPaginator = loader;`
  and, inside the success callback, `:127-129`
  `filters.page = json.page + 1; page.asyncPaginator = model.bind(...); page.haveMore(true);`.
  A `resetList` helper (`view.ts:63-68`) explicitly nulls it —
  `page.asyncPaginator = null` at `:66` — before rebuilding, on filter change.
  **[I]** dailymotion and trakt are the same author and share this template; count them as
  one design, two instantiations.
- **Search.** **All three mechanisms at once.** Two global Searchers (`dailymotion.ts:88`
  users, `:92` videos), three own routes (`:65,69,73`), and an item of type `'search'` on
  the home page (`support/view.ts:173`). **[I]** The two-Searcher split exists because a
  Searcher contributes one titled section to the aggregated results page (§0.2), so
  "users" and "videos" need separate registrations — there is no way to emit two sections
  from one Searcher.
- **Service.** `dailymotion.ts:35` `service.create(PLUGIN_NAME, general.PREFIX + ":start", PLUGIN_DESCRIPTOR.category, true, plugin.getIconPath())`
  — the only plugin that reads the service `type` **out of the manifest's `category`**
  rather than hard-coding it.
- **Metadata.** `support/view.ts:18-45`, per-item-type appenders returning the `Item` so
  callers can `moveBefore` it (`view.ts:100`).

### 1.9 soap4.me — ES2015 modules → Babel, 2016, `import {Route, Searcher} from 'showtime/page'`

- **Routes.** The **only fully data-driven registration**: `src/index.js:54-62` defines a
  `routes` map of pattern strings built by a `prefix()` helper, `src/index.js:150+`
  defines a `handlers` object keyed by those same pattern strings using ES2015 computed
  keys (`[routes.START](page) {...}`), and `src/index.js:427-434`:

  ```js
  [routes.START, routes.SERIES, routes.SEASON, routes.EPISODE,
   routes.LOGIN, routes.LOGOUT].forEach((route) => new Route(route, handlers[route]));
  ```

  **[I]** Pattern and handler are joined by identity rather than by adjacency — the only
  registration in the corpus where the route string cannot drift from its handler.
- **Arguments.** Positional captures, embedded in the `prefix()` composition:
  `src/index.js:59` `EPISODE: prefix('browse', '([0-9]+)', 'season', '([0-9]+)', 'video', '([0-9]+)')`.
  **[M]** It is the only plugin that constrains captures to `([0-9]+)` instead of `(.*)`.
  **[I]** This does **not** raise its route priority — `strcspn` (`es_route.c:145`) stops
  at the first `(` either way — but it does buy correctness: a non-greedy character class
  cannot over-match into the next path segment, which is exactly the failure mode
  m7-jellyfin and dailymotion are exposed to (§1.3, §1.8).
- **Pagination.** **None.** **[M]** grep for `haveMore|paginator|Paginator` across
  `movian-soap4.me/src` returns zero hits. Every page renders its full data set
  (`src/index.js:171-177` renders four complete sections).
- **Search.** Global `Searcher` only — `src/index.js:414`
  `const search = new Searcher(title, iconPath, handlers[routes.SEARCH]);`.
  **[M]** `routes.SEARCH` is defined at `:56` but is **deliberately absent** from the
  `Route` registration array at `:427-434`, so the same handler is *only* reachable as a
  global searcher. **[I]** The most explicit "global search is the search UI" stance in
  the corpus.
- **Service.** `src/index.js:413` `Service.create(title, routes.START, category, true, iconPath)`,
  where `title`/`category`/`icon`/`id`/`i18n` are destructured from
  `JSON.parse(Plugin.manifest)` at `:10-19` — the idiom map #19 flagged.
- **Metadata.** `src/index.js:477-488` — `{title, description, icon}` with icons derived
  from a URL convention, and a leading `'separator'` item per section (`:455`).

---

## 2. Cross-corpus tallies (measured)

| plugin | route form | args | pagination | search | service `type` |
|---|---|---|---|---|---|
| HDRezka | 17 × inline `new page.Route` in `init()` | shared 6-group `ROUTE_PATTERN` + opaque payload | `asyncPaginator` + delay/token/watchdog | Searcher **and** own route | `video` |
| trakt | 40 × inline, one file | positional, ≤4 | `asyncPaginator`, reassigned to API thunk | own route + `'search'` item | `video` |
| m7-jellyfin | table `{path, view}` + `forEach` | positional, `.bind(this)` | `asyncPaginator`, offset/total, `setTimeout(125)` | own route + `'search'` item | `video` |
| anilibria | 4 × inline | 1 positional | `asyncPaginator` via `lib/pagination.js` module | Searcher only (no `new`) | `video` |
| youtube | 20 × inline, incl. 6 foreign http(s) URLs | positional, shared named handlers | `asyncPaginator`, `pageToken` cursor | `'search'` item + own route, **no Searcher** | `video` |
| qobuz | 5 × inline | 1 positional | **synchronous `paginator`** | Searcher **and** own route | `music` |
| tmdb | 24 × `plugin.addURI` (v1) | positional, ≤3 | `page.paginator`, drains all pages in a `while(true)` | own routes, **no `addSearcher`** | `video` |
| dailymotion | 13 × inline | positional, own `decodeURIComponent` | `asyncPaginator`, reassigned | **2 Searchers + own routes + `'search'` item** | from manifest `category` |
| soap4.me | data-driven `routes`/`handlers` maps | positional `([0-9]+)` | **none** | Searcher only | from manifest `category` |

Counts: **9/9** register exactly one service with `enabled = true` and a `:start` URL.
**9/9** use positional regex captures — no plugin invented a query-string or JSON-in-URL
convention at the route layer (HDRezka comes closest, but it still arrives as captures).
**6/9** use `asyncPaginator`; **2/9** use `paginator`; **1/9** paginates not at all.
**5/9** register a `Searcher`; **4/9** use the `'search'` item type; **6/9** serve a
`:search:(.*)` route of their own; **3/9** (HDRezka, qobuz, dailymotion) do both Searcher
and own route.

---

## 3. Which of these has ONE obvious way

These need the canon only to *record* the answer, not to choose one.

1. **Route registration mechanism.** `new page.Route(pattern, handler)` — 9/9 (tmdb via
   the v1 shim, which is literally that call, `legacy/api-v1.js:112-115`). There is no
   alternative in the API.
2. **How arguments reach the handler.** Positional regex capture groups after the Page —
   9/9, because `page.js:394-396` offers nothing else.
3. **How a service is created.** `service.create(title, url, type, enabled, icon)` with
   `url = PREFIX + ':start'` — 9/9, identical five arguments, identical URL convention.
4. **What makes it appear on the home screen.** `enabled` truthy → `$global.services.enabled`
   (`service.c:116-124`). There is no second mechanism.
5. **How an item is added.** `page.appendItem(url, type, metadataObject)` — 9/9. Passive
   items via `appendPassiveItem`, separators via `appendItem('', 'separator', {title})`
   (HDRezka `catalog.js:135`, soap4.me `index.js:455`, jellyfin `view.js:233`, anilibria
   `ui.js:16`) — a convention that converged without documentation.

## 4. Which genuinely have several — the canon must choose

1. **Pagination: `asyncPaginator` vs `paginator` vs neither.** Not a style split; the two
   are *semantically different contracts* (§0.4) and the corpus splits 6/2/1. **[I]
   Recommendation: canonicalise `asyncPaginator`.** Reasons, all measured: the core
   returns early on it (`page.js:208-211`) so it composes with callback HTTP; `paginator`
   is synchronous and its one correct user (qobuz) works only because its HTTP is
   blocking; its other user (tmdb) got it structurally wrong (`tmdb.js:263-300`) and
   half-disabled it in the second copy (`:2466`). Canon must also state the corollary the
   corpus discovered the hard way: *with `asyncPaginator` you own `haveMore`*.
2. **Where the pagination loop lives.** Four shapes exist: reassign-the-continuation
   (trakt `view.js:141-143`, dailymotion `view.ts:127-129`), fixed-loader-plus-cursor
   (youtube `browse.js:274-275`, jellyfin `view.js:254`), extracted state machine
   (anilibria `lib/pagination.js`), inline with hand-rolled cancellation (HDRezka
   `catalog.js`). **[I] Recommendation: the extracted state machine.** It is the only one
   that is unit-testable (`anilibria/tests/pagination.test.js`) and it already
   generalises the two hazards the corpus hit independently.
3. **The `haveMore(true)` storm.** Three plugins independently added a delay before
   exposing more items — HDRezka 1200 ms/50 ms (`catalog.js:10-13`), anilibria the same
   constants (`lib/pagination.js:37-38`), jellyfin 125 ms (`view.js:225`). **[I]** Two of
   those are one author, so this is convergence of *two* parties, not three. Still, the
   canon has to say something: either a required delay, or a core fix. **Recommendation:
   record it as a required idiom with a stated reason, and file a core issue** — a UI
   behaviour that every serious plugin must work around does not belong in plugin code.
4. **Search integration.** Three mechanisms, and no plugin uses all three except
   dailymotion. **[I] Recommendation: an in-page `'search'` item + own `:search:(.*)`
   route is primary; a `Searcher` is an additional, optional contribution to the global
   search page.** Evidence for primary: andoma's own plugin does exactly this and
   registers **no** Searcher (`youtube.js:224` + `:117`). Evidence that Searcher is
   secondary and constrained: a Searcher page is `flat`, so it has **no `page.options`**
   (`page.js:196-200`, `:429`); it contributes exactly one titled section, which is why
   dailymotion needs two registrations (`dailymotion.ts:88,92`); and a throwing Searcher
   damages a shared page, which qobuz guards for explicitly (`qobuz.js:427-430`). The
   canon should also mandate `new` (anilibria `anilibria.js:79` omits it) and require the
   `icon` to be a real path (HDRezka `routes/index.js:61` passes `'search'`).
5. **Route-registration shape.** Inline calls (7/9) vs a table (m7-jellyfin
   `view.js:14-56`) vs pattern/handler maps (soap4.me `index.js:54-62,427-434`).
   **[I] Recommendation: the map/table form** — it is the only shape where the pattern
   string and its handler cannot drift apart, and it makes registration order (§0.1)
   inspectable in one place, which is exactly where the two ordering hazards below live.
6. **Route ordering and specificity.** The core's priority rule (`es_route.c:145`) is
   `strcspn` to the first metacharacter, which is invisible to authors and **ties** for
   the common `foo:(.*)` vs `foo:(.*):bar` pair — present in m7-jellyfin (`view.js:32-39`)
   and dailymotion (`dailymotion.ts:53/61`, `:77/81`). **[I] Recommendation: the canon
   states a rule authors can follow without knowing `strcspn` — anchor patterns with `$`
   or use a non-greedy/character-class capture, and register the most specific first.**
7. **`page.type` and whether to ship a `.view`.** `'directory'` (most), `'raw'` +
   `metadata.glwview` (HDRezka `catalog.js:20-22`), `'home'` (jellyfin `view.js:92-94`), and
   `page.contents`/`page.model.contents` set to `'grid'`/`'list'`/`'movies'` (jellyfin
   `view.js:170-171`, anilibria `anilibria.js:106`, tmdb `:297`, soap4.me `:157-158`).
   **[I]** Out of this ticket's scope but adjacent to it; belongs with map #19's "GLW views
   in plugins" fog. Flagging, not deciding.
8. **Item metadata vocabulary.** No schema exists (`page.js:271`). The skin reads ~20 keys
   (§0.6) and ignores the rest. **[I] Recommendation: the canon publishes the measured key
   list and marks `title` + `icon` as the floor** — every plugin in the corpus sets exactly
   those two at minimum.
9. **Watched-state binding for non-`videoparams:` URLs.** The core auto-binds only for
   `type == 'video'` with a parseable `videoparams:` URL (`page.js:273-293`). HDRezka is
   the only plugin that noticed and rebinds by hand
   (`utils/ui.js:27-33` + `catalog.js:161`). **[I]** Every other plugin appending
   `'video'` items with plain plugin URLs is silently getting play-info bound to that
   plugin URL rather than to a stable canonical id. The canon should say which one an
   author wants.

---

## 5. Divergences from the teaching examples

Where the ticket asked me to check real plugins against the examples, the examples lost.

### 5.1 `async_page_load` — correct, and matched by the corpus

**[M]** `plugin_examples/async_page_load/async_page_load.js:26-28`:
`page.type = "directory"; page.asyncPaginator = loader; loader();` — install then call,
with the loader owning `page.haveMore(true|false)` at `:12,21`. This is exactly what
youtube (`browse.js:274-275`), jellyfin (`view.js:254-255`), trakt (`view.js:150-151`)
and dailymotion (`view.ts:142-143`) do. **[I]** The one thing it under-teaches is
re-entrancy: it has no load mutex and no cancellation token, which is precisely what
HDRezka (`catalog.js:26-27,68-69,126`) and anilibria (`lib/pagination.js:44-45,71-75,88`)
both had to add.

### 5.2 `02-intermediate/04-search-provider` — **calls API that does not exist**

**[M]** `/home/uzver/plugin_examples/02-intermediate/04-search-provider/main.js:56`
sets `page.searchable = true` and `:59` assigns `page.onsearch = function (query) {...}`.
**[M]** Neither member exists on `Page` (§0.2 — the full member list from
`page.js:150-374`); both are plain property assignments that nothing ever reads.
**[I]** The "searchable directory with autocomplete" half of this example is dead code
and will silently do nothing. The correct spelling of what it is reaching for is the
`'search'` item type (§0.3), which four plugins use and this example does not mention.
**[M]** The Searcher half (`:23-48`) is correct.

### 5.3 `02-intermediate/05-pagination` — **teaches neither pagination contract**

**[M]** `/home/uzver/plugin_examples/02-intermediate/05-pagination/main.js:55` assigns
`.onSelect` to the object returned by `appendItem`. **[M]** `Item` has no `onSelect`
member — its prototype is `bindVideoMetadata`, `unbindVideoMetadata`, `toString`, `dump`,
`enable`, `disable`, `destroyOption`, `addOptAction`, `addOptURL`, `addOptSeparator`,
`destroy`, `moveBefore`, `onEvent` (`page.js:21-148`). The "Load More…" button therefore
does nothing when activated. **[M]** `main.js:66` compounds it with
`arguments.callee` (legal in Duktape non-strict, but it is inside a handler that never
runs).
**[M]** The file never mentions `asyncPaginator`, `paginator`, or `haveMore` — the three
mechanisms the core actually implements (§0.4) and that 8 of 9 plugins use. Its "Pattern
2" (numbered pages via `example:paginate:pages:(.*)`, `:74-110`) is real, but no plugin in
the corpus paginates that way.
**[I]** As the intended teaching form for pagination this example is not merely
incomplete, it is misleading; the canon should replace it with something shaped like
`async_page_load` plus the mutex/token that real plugins all added.

---

## 6. Surprises worth carrying into the canon

- **`page.paginator` and `page.asyncPaginator` are not two spellings of one idea.** One is
  sync-with-return-value, the other is async-and-you-own-`haveMore`, and setting the first
  implicitly asserts `haveMore(true)` (`page.js:186-192`). No plugin's comments show
  awareness of this except qobuz's, which cites the core line number
  (`qobuz.js:269-270`).
- **The author of Movian did not use `Searcher` in his own plugin.** youtube's search is a
  `'search'` item plus a plain route (`youtube.js:224`, `:117`).
- **Route priority is `strcspn(pattern, "()[]*?+$")`** (`es_route.c:145`) — an
  implementation detail no plugin could have guessed, that silently ties the most common
  overlapping-pattern pair.
- **A Searcher page has no `page.options`** because it is constructed `flat`
  (`page.js:429` → `:196-200`). Any plugin that reuses one view function for both a route
  and a Searcher will get an undefined-property throw the first time it touches
  `page.options` — dailymotion (`view.ts:70-71`) guards with `if (page.options)`;
  m7-jellyfin's `showSearch` (`view.js:167-190`) does not touch options, so it escapes.
- **Two of the three "teaching" examples call API that does not exist** (§5.2, §5.3), and
  they are not even in the core repo — they live in an untracked tree at
  `/home/uzver/plugin_examples/`.
- **Three plugins independently added a sleep before `haveMore(true)`** to stop the GLW
  cloner from immediately demanding another page (HDRezka `catalog.js:10-13`, anilibria
  `lib/pagination.js:37-38`, m7-jellyfin `view.js:225`). Two share an author; it is still
  the loudest unaddressed core behaviour the corpus reveals.
- **tmdb's paginator drains the entire result set in a `while(true)`** on first call
  (`tmdb.js:263-300`), and the second copy of the same function has the
  `page.paginator = paginator` line commented out (`:2466`).
- **anilibria calls `page.Searcher(...)` without `new`** (`anilibria.js:79`) and it works
  by accident (§1.4).
- **m7-jellyfin declares `service` three times at the top of its entry point** —
  `src/jellyfin.js:1` `const service = require('movian/service')`, `:3`
  `var service = require('movian/service')`. **[I]** Under ES2015 semantics this is a
  redeclaration error; it survives because swc transpiles to `var`. Not in this ticket's
  scope, but it is evidence that the transpile step is load-bearing in ways its author may
  not intend.
- **`apiversion` defaults to 1, not 2** (`src/plugins.c:688`), and tmdb is v1 purely
  because its manifest omits the field. The v1 `plugin` object is a 40-line shim
  (`legacy/api-v1.js:104-121`) over the identical v2 calls.
