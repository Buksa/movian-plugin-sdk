---
name: authoring
description: >-
  How a Movian plugin is written — the idioms, dialect and mechanism choices that no
  artifact carries. Use before writing or changing plugin JS — the entry point and its
  scope, service and route registration, page items and metadata, pagination, search,
  HTTP and caching, settings. What the API *is* comes from movian:api and the generated
  .d.ts; this is what to do with it.
---

# Authoring a Movian plugin

Derived from the nine plugins that exist — HDRezka, trakt, m7-jellyfin, anilibria,
youtube, qobuz, tmdb, dailymotion, soap4.me — and from the core that runs them.
**No authoring documentation ever existed**, so this does not codify common practice;
it records where independent authors converged (the API led them there) and chooses
where they diverged (it did not).

## Reading the evidence tags

Every rule carries one. **The tag is your permission to deviate.**

| tag | means | deviate |
|---|---|---|
| `[CORE]` | read out of the core's own source | never — it is how the C behaves |
| `[9/9]` | all nine do it because the API offers nothing else | never |
| `[n/9]` | measured convergence among independent authors | with a reason |
| `[AUTHOR]` | andoma's youtube — the only evidence of *intended* use | with a reason |
| `[COPIED]` | one author did it, others took it verbatim | freely — it is one decision, not N |

`[COPIED]` exists because counting is dishonest on its own: trakt's `src/auth.js` is a
near-verbatim descendant of youtube's `api.js`, three comments word-for-word, and
anilibria's `lib/pagination.js` is HDRezka's loop extracted by the same author.

## The dialect

**Duktape runs ES5.1 and nothing later.** `[CORE]` No `let`/`const`, no arrow functions,
no template literals, no `class`, no `Promise`, no `Object.entries`. That is the
never-deviate part.

**So write ES5.1 by hand, and do not add a build step for a new plugin.** `[6/9]` Six of
nine write ES5 directly — proven by parsing every shipped file with acorn at
`ecmaVersion: 5`. This is the corpus majority and the recommended default, not a core
constraint: three plugins do build, and the guidance for an existing build tree is below.

- Take types from the generated `.d.ts` with `"noEmit": true`. Three plugins already do
  exactly that; it is not a build step. The working config:

  ```json
  {
    "compilerOptions": {
      "allowJs": true, "checkJs": true, "noEmit": true,
      "target": "ES5", "lib": ["ES5"], "moduleResolution": "node", "types": []
    },
    "include": ["<entry>.js", "lib/**/*.js", "types/**/*.d.ts"]
  }
  ```

  **Make `include` cover every file you ship.** A file outside it is not checked and
  reports nothing — which reads exactly like a clean pass.
  `require('movian/page')` resolves to the declared module in the entry file as well as
  in `require`d ones, so the entry is checked too.

### Check the artifact before you trust it

**Everything this skill says about type checking depends on the core your `.d.ts` came
from, and a checkout can be months behind without saying so.** Two things arrived in the
core during 2026-08 that the typing rules here require:

```sh
grep -c 'interface Page'   "$(mdev core)/generated/movian-api.d.ts"   # need >= 1
grep -c 'declare const Plugin' "$(mdev core)/generated/movian-api.d.ts"   # need >= 1
```

- **No `interface Page`** → `movian/page` exports only `Route` and `Searcher` as
  `new(…): any`, so the handler parameter is `any`, the JSDoc `import(…).Page` form
  fails with TS2694, and **no invented member is caught anywhere**.
- **No `declare const Plugin`** → the config above reports TS2304 on `Plugin`,
  `console` and `setTimeout` before you have written anything unusual.

If either is missing, regenerate (`support/devtools/metadata/gen.py`) or pull the core.
Measured the hard way: a from-scratch author on a checkout four merges behind had to
hand-transcribe `Page` and `Item` out of `res/ecmascript/modules/movian/page.js` to get
any checking at all, and the clean `tsc` run before that was **vacuous**. Mutation-test
your own gate — write `page.searchable = true` and confirm it reddens — before believing
a green one.
- **A compiler that emits ES5 accepts ES6 in silence.** `tsc --target ES5` downlevels a
  template literal instead of rejecting it, so the check goes green and Duktape throws
  `SyntaxError: invalid token` at load. That is the mechanism that hid a real dialect
  error rather than catching it.
- **Verify by loading, never by compiling.** `mdev run -p .` — see `movian:run`.
- Where a build already exists, edit the **source**, never the artifact (HDRezka ships
  both). None of the three build-requiring trees in the corpus loads as checked out.
- A transpiler never supplies the *library*: m7-jellyfin still hand-writes
  `Object.entries` in `src/polyfill.js`.

## Identity comes from the manifest

```js
var manifest = JSON.parse(Plugin.manifest);   // the raw text of plugin.json
var PREFIX   = manifest.id;
var LOGO     = Plugin.path + manifest.icon;
```

`[5/9]` — the corpus's clearest consensus, reached independently and undocumented
(HDRezka, trakt, anilibria, m7-jellyfin, soap4.me). `[CORE]` `ecmascript.c:900` pushes
the manifest **text** onto the global `Plugin` for every plugin, so every consumer must
`JSON.parse` it.

`[AUTHOR]` youtube hardcodes `"Youtube"` and `"youtube"` instead, duplicating its own
manifest. **Here the community is right and the author is not** — nothing stopped him,
and this is the clearest case where *intended* and *good* diverge.

## The entry file, and the scope trap

The entry registers what the plugin offers and returns. It does not loop or block.

`[CORE]` `ecmascript.c:839` compiles the entry with `duk_pcompile(ctx, 0)` — **program
code**, so a top-level `var` in the entry file becomes a global. Files reached by
`require()` go through Duktape's CommonJS wrapper and are function-scoped. That
asymmetry is why youtube's `browse.js` can read `PREFIX` without importing it.

**Do not rely on it.** Pass values explicitly. The corpus's module-using plugins all do,
and the alternative is an invisible dependency between two files.

**`require()` inside route handlers, not only at the top.** `[AUTHOR]` with the author's
stated reason at `youtube.js:8-9` — *"keep the main youtube.js file small for faster
loading on slower devices"* — and independently converged on by HDRezka (63 sites) and
trakt (7).

**`require('native/*')` is a smell.** `[AUTHOR]` The author flags his own lines:
`youtube.js:45` and `api.js:4` both carry `// XXX: Bad to require('native/')`. Use the
`movian/*` wrapper when one exists; when none does (`native/io.httpInspectorCreate`),
say so in a comment.

## The service — how the plugin appears at all

```js
service.create(manifest.title, PREFIX + ':start', 'video', true, LOGO);
```

`[9/9]` — five arguments in that order, identical `:start` URL convention, exactly one
service per plugin, `enabled` truthy. Only the *third* argument varies, and the section
on it below says how. The call itself differs in one plugin: tmdb reaches it as
`plugin.createService` (`tmdb.js:24`), the apiversion-1 spelling of the same function.
`[CORE]` `service.c:116-124` filters on `enabled`,
and that is the only gate — there is no separate "register on home" call.

**The home screen clones `$core.services.stable`, not `.enabled`.** `[CORE]`
`glwskins/flat/pages/home.view:111`. `stable` is a `prop_reorder` over the same
enabled-filtered set (`service.c:126-138`), so the rule is unchanged — but debugging the
home screen against `services/enabled` inspects the wrong node.

**Always pass a real `icon`, because `type` doubles as an icon key.** `[CORE]`
`home.view:129-140` falls back to `"skin://icons/" + translate($self.type, …)` when
`$self.icon` is unset, and its table covers only `tv`, `usb`, `cd`, `dvd`, `bluray`,
`network`, `setting`, `storage`, `plugin`, `movian` — **`video` and `music` are not in
it**, so the two types the whole corpus uses would render as a generic folder. All nine
pass an icon, which is why nobody has noticed.

`type` is `'video'` for eight of nine; qobuz uses `'music'`. dailymotion and soap4.me
read it from the manifest's `category` — `[2/9]`, and it inherits the hazard above:
`category: "other"` is in no icon table either.

## Routes

```js
new page.Route(PREFIX + ':release:([0-9]+)', function(page, id) { ... });
```

`[9/9]` — `new page.Route(pattern, handler)`, and the handler receives
**`(Page, ...captureGroups)`**. `[CORE]` `page.js:384-406` offers no options object, no
named parameters and no query-string parsing: positional regex captures are the only
channel from URL to handler. Only 8 capture slots exist (`es_route.c:171`).

`[CORE]` A pattern not starting with `^` is silently anchored at the front
(`es_route.c:109-115`) and **is not anchored at the end**. Registering a pattern string
twice throws `"Route %s already exist"`.

### The priority rule, and the tie it creates

`[CORE]` `es_route.c:145`:

```c
er->er_prio = strcspn(str, "()[]*?+$") ?: INT32_MAX;
```

**Read that line together with the one above it.** `es_route.c:108-114` prepends `^`
when the pattern lacks one, so the string scored at `:145` always begins with `^` — which
is **not** in `"()[]*?+$"`. `strcspn` therefore always returns at least 1, always truthy,
and **the `?: INT32_MAX` fallback is unreachable**. Do not reason from it.

What is left is simple: **priority is the length of the literal prefix** — the offset of
the first metacharacter, or the whole length when there is none. The list is sorted
descending and the first match wins (`es_route.c:95-98`, `:189-199`).

So **the longer literal prefix wins, and nothing else matters.** A literal route does not
automatically outrank a pattern route: `foo:x` scores 6 and loses to
`foo:catalog:(.*)`, which scores 12.

**This ties for the most common overlapping pair.** `foo:(.*)` and `foo:(.*):bar` both
stop at the same `(`, so they get equal priority and the winner is insertion order —
and `(.*)` is greedy and unanchored, so the shorter pattern can swallow the longer
URL. Present in m7-jellyfin (`src/view.js:32-39`) and dailymotion
(`dailymotion.ts:53/61`, `:77/81`).

**Rules you can follow without knowing `strcspn`:**

1. Constrain captures — `([0-9]+)`, `([^:]+)` — never bare `(.*)` in a pattern that has
   a longer sibling. `[1/9]` soap4.me is the only plugin that does this, and it is right.
2. End-anchor with `$` where the URL is complete — **for matching, never for
   precedence.** `$` is itself in the metacharacter set, so a trailing one is scanned
   past nothing and leaves the score unchanged; it can never raise priority. It stops
   `(.*)` from over-matching, which is the real problem.
3. Register the most specific pattern first — it is the tiebreak, and after rule 1 there
   is nothing else left.

**Exception: the search route takes everything.** `[CORE]` The search bar concatenates
raw — `theme.view:227` is `navOpen(URLPREFIX + $view.searchQuery)`, no escaping — and
captures reach the handler **undecoded**: `es_route.c:236-240` pushes the raw byte range.
So a query arrives with its spaces, colons, parens and non-ASCII intact. Write
`:search:(.+)$` and decode nothing; `([^:]+)` there silently truncates every multi-word
query and every `subject:x` link you emit yourself. Only dailymotion runs
`decodeURIComponent` on a capture, and it does so only on its own route — its Searcher
path passes the query through undecoded, so the two disagree.

### Keep pattern and handler together

Register from a table or a map, not from a scattered list of inline calls.

```js
var routes = { START: PREFIX + ':start', RELEASE: PREFIX + ':release:([0-9]+)' };
var handlers = {};

/** @param {import('movian/page').Page} page */
handlers[routes.START] = function(page) { ... };

/** @param {import('movian/page').Page} page @param {string} id */
handlers[routes.RELEASE] = function(page, id) { ... };

[routes.RELEASE, routes.START].forEach(function(pattern) {
  new page.Route(pattern, handlers[pattern]);
});
```

`[2/9]` — m7-jellyfin's `{path, view}` table and soap4.me's pattern/handler maps. It is
the only shape where the pattern string cannot drift from its handler, and it puts
registration order (which decides ties, above) in one inspectable place. Seven of nine
use scattered inline calls; trakt has forty in one file.

**The JSDoc line is not decoration — the table form costs you the type check without
it.** Measured: `new page.Route(pat, function(p) { p.contents = 'x'; })` reports
TS2339 because the declared callback signature contextually types `p` as `Page`; the
same body stored in a table and registered by reference reports nothing, because the
function expression is written where nothing types it. Route handlers are where almost
all plugin code lives, and invented members are the largest failure class, so a shape
that silently un-types them is only worth it annotated.

If a handler is a method, `.bind(this)` it — the Page-first contract gives the handler
no receiver.

### Claiming a URL space

`[AUTHOR]` youtube is the only plugin reachable from a URL that is not its own:
`plugin.json:14-22` declares `control.uriprefixes`, paired with routes for raw
`youtube.com` / `youtu.be` URLs. `[CORE]` `plugins.c:2211-2221` feeds that list to the
on-demand plugin-install trigger. The design it expresses: **a plugin is a handler for a
URL space, not an app behind an icon.** Every other plugin is reachable only through its
home-screen icon.

## Items and metadata

`[9/9]` `page.appendItem(url, type, metadataObject)`. `[CORE]` `page.js:263-297` assigns
`root.metadata = metadata` wholesale and deep-copies it into the prop tree. **There is no
schema and no validation** — an unread key is silently inert.

- **The floor is `title` + `icon`.** Every plugin in the corpus sets exactly those two at
  minimum.
- The keys the flat skin actually reads, by frequency: `title`, `icon`, `duration`,
  `start`/`events`/`stop` (EPG), `episode`, `year`, `tagline`, `rating`, `glwview`,
  `description`, `backdrop(s)`, `artist`, `season`, `subtitle`, `synopsis`, `track`.
  Anything else needs your own `.view`.
- **`metadata.icon` renders; `metadata.logo` does not — it feeds bookmarks.** `[CORE]`
  `theme.view:167` and the item views read `icon`; `navigator.c:707` subscribes to
  `page/model/metadata/logo` and routes it to the bookmark icon, under
  `#if ENABLE_BOOKMARKS`. Four plugins write `logo`; they are setting a different thing,
  and probably not on purpose.
- **`subtype` on an item is a Material icon name.** `[AUTHOR]` `youtube.js:234`
  `'subscriptions'`, `browse.js:211` `'thumb_up'`. `[CORE]`
  `glwskins/flat/items/list/default.view:19-20` resolves it as
  `"ic_" + $self.subtype + "_48px"`; 82 icons exist in that directory. Nobody else found
  this.
- Separators are `page.appendItem('', 'separator', {title: ...})` — `[4/9]`, converged
  without documentation.
- **The layout hint is `page.model.contents`, not `page.contents`.** `[CORE]`
  `glwskins/flat/pages/directory.view:47,58` reads `$self.model.contents`; `Page` has no
  `contents` accessor, so the shorter spelling is inert. Four plugins write the real one;
  tmdb writes only the inert one; m7-jellyfin and soap4.me write **both, with different
  values** on the same page (`model.contents = 'grid'` beside `contents = 'list'`).
  Values the core itself sets: `grid`, `plugins`, `searchresults`.
- **Watched state binds for every `'video'` item, whether you want it or not.** `[CORE]`
  `page.js:275` sets `metabind_url = url` and `:292` calls `bindPlayInfo(root,
  metabind_url)` **unconditionally** for `type === 'video'`. The `videoparams:` branch at
  `:276-291` only *refines* the key from `canonicalUrl` or the first source. So an item
  whose URL is your own plugin route gets watched state and resume keyed on **that
  route** — which breaks the moment your payload format changes.

  **Binding a second time does not replace the first.** `[CORE]`
  `playinfo.c:252-289` allocates a fresh record, takes the same `playcount` /
  `lastplayed` / `restartpos` props via `prop_create_r`, and `LIST_INSERT_HEAD`s it — it
  never looks for an existing binding on that prop. Worse, its `mip_set` writes with
  `prop_set_int_ex(…, mip_playcount_sub, …)` (`:158`), which excludes only *its own*
  subscription: the first binding's callback still fires and writes the new value into
  the **old** URL's kvstore row (`:241-243`).

  So if you need a stable key, give the item a URL you control the shape of, or accept
  two live bindings. HDRezka is the only plugin that noticed the instability and adds a
  synthetic canonical binding (`utils/ui.js:27-33`, called from `pages/catalog.js:161`
  right after appending a `'video'` item) — which leaves it with both.

## What actually renders, and clearing the spinner

**Which item views apply depends on `page.model.contents`, and there are two sets.**
`[CORE]` `directory.view:58` maps `contents` to a page view, and each page view picks a
different item directory:

| `contents` | page view | item views |
|---|---|---|
| unset, most values | `list.view:33` | `items/list/<type>.view` → `list/default.view` |
| `grid`, `images` | `grid.view:34` | `items/rect/<type>.view` → `rect/default.view` |
| `searchresults` | `searchresults.view:36` | `items/rect/…` |

`items/list/` has 18 views — `separator`, `info`, `video`, `audio`, `image`, `person`,
`event`, `tvchannel`, `tvepisode`, `action`, `station`, `plugin`, `location`, `network`,
`font`, `add`, `search`, `default`. **`items/rect/` has 8** — `audio`, `image`, `plugin`,
`search`, `separator`, `station`, `video`, `default`. So on a grid page most types you
can name fall through to `rect/default.view`, including `info`.

The two defaults do not draw the same things either: `list/default.view` reads
`metadata.icon` and `metadata.title`; `rect/default.view` reads `metadata.backdrop`,
`metadata.icon` and `metadata.title`. Everything else in your metadata object is inert
until you name a type whose view reads it, or ship your own `.view`. Fold the author, the
year or the rating into the title string if you want them on a stock list. An item with
no `metadata.icon` draws a placeholder glyph, not nothing.

**Check the pair you are actually rendering.** A plugin whose landing page is a grid and
whose detail page is a list is using both sets at once — which is easy to write without
noticing.

**Set `page.loading = false` when your data arrives.** Nothing does it for you on an
async page, and the page spins forever otherwise. `page.error(msg)` clears it as a side
effect, which is why an error path can look like it works while the success path hangs.

`page.entries` is what the search-results header counts ("20 hits"). Set it to the
result total when you know it.

An unknown type falls back to `default.view` — which is why
`appendPassiveItem('label', …)` works for HDRezka and qobuz despite there being no
`label.view` in either set.

**`string`, `bool`, `integer` and `multiopt` are settings widgets, not text.**
`string.view` is a focusable text *input* bound to `$self.value`. Passing prose to it
gives the user an edit box.

**Detail pages: `appendPassiveItem` does not put your text where a view reads it.**
`[CORE]` `page.js:320-331` writes the second argument to `root.data`, while
`items/list/info.view:10` renders `$self.description` — a top-level item prop that no
`appendPassiveItem` argument reaches. Assign it through the returned item:

```js
var it = page.appendPassiveItem('info', '', {icon: cover});
it.root.description = synopsis;
```

`[7/9]` use `appendPassiveItem`, but almost entirely for `separator` and for
icon+title rows through the `default` fallback. The three plugins with rich detail pages
(HDRezka, tmdb, trakt — the only three shipping `.view` files) bypass all of this and set
`page.metadata.glwview` instead.

## Pagination

**`paginator` and `asyncPaginator` are not two spellings of one idea.** `[CORE]`
`page.js:202-235` — both are served by one `wantmorechilds` subscription, and:

- `asyncPaginator` short-circuits and returns (`:208-211`). **You own `haveMore`
  entirely.**
- `paginator` is synchronous; its **return value** is the more-items flag and the core
  sets `haveMore` for you (`:213-225`). Merely assigning `.paginator` implicitly calls
  `haveMore(true)` via the accessor at `:186-192`.
- If both are set, `asyncPaginator` wins and `paginator` is dead code.

**Use `asyncPaginator`.** `[6/9]` and the reason is structural: it composes with
callback HTTP, while `paginator` blocks the Duktape context and is viable only where
requests are synchronous. Its one correct user is qobuz; its other user, tmdb, got it
wrong — `tmdb.js:263-300` drains the entire result set in a `while(true)` on first call,
and a second copy of the same function has the assignment commented out.

**Install, then call:**

```js
page.type = 'directory';
page.asyncPaginator = loader;
loader();
```

`[4/9]` and matched by the `async_page_load` example. **Order decides whether the first
load counts as pagination.** Assigning `asyncPaginator` and then calling `loader()`, as
above, means the first batch runs through the same path as every later one. youtube does
the reverse — loads once, *then* assigns (`browse.js:274-275`) — so its first page is not
pagination and a re-filter can reset the cursor without racing the paginator. Pick
deliberately; both appear in the corpus.

**What the example under-teaches, and every real plugin added:** a load mutex, a
monotonic cancellation token, and a watchdog that releases the mutex if the fetch hangs
(HDRezka `pages/catalog.js:26-27,68-69,115-126`; anilibria `lib/pagination.js:44-45,71-88`).
Prefer extracting that loop into a module with an injectable scheduler — `[COPIED]`, one
author, but it is the only shape in the corpus that is unit-testable.

`setTimeout` / `clearTimeout` / `setInterval` / `clearInterval` are globals `[CORE]`
`es_timer.c:239-241` — no `require`. They are the only timing primitive you get, and
both the watchdog and the delay below need them.

**Delay `haveMore(true)`.** `[2/9]` GLW cloners request more children
immediately when `haveMore(true)` is set while every card is on screen, so a fast (or
cached) page triggers runaway pagination. HDRezka waits 1200 ms on the first page and
50 ms on a cache hit; m7-jellyfin arrived at `setTimeout(…, 125)` separately. This is a
workaround for core behaviour, not a design — but every serious plugin needs it.

## Search — three mechanisms

1. **An item of type `'search'` on your own page**, plus your own `:search:(.+)$` route.
   `[CORE]` `glwskins/flat/items/list/search.view` renders an inline search box that
   navigates to `<url><query>` on Enter.
2. **`new page.Searcher(title, iconPath, callback)`** — a global hook contributing one
   titled section to the aggregated search page.
3. Your own route alone, reached some other way.

**Canon: (1) is primary; (2) is an optional extra contribution.** `[AUTHOR]` youtube
registers **no** Searcher and uses the `'search'` item — `youtube.js:224` plus the route
at `:117` — and `Searcher` had existed since 2014, so that is a choice, not an absence.

If you also register a Searcher:

- **Use `new`.** anilibria calls `page.Searcher(...)` without it; it works by accident
  (non-strict `this`) and loses the `destroy()` handle.
- **Pass a real icon path.** HDRezka passes the bare string `'search'`, which
  `page.js:425` assigns straight to `metadata.icon`.
- **A Searcher page is `flat`, so it has no `page.options`.** `[CORE]`
  `page.js:429` → `:196-200`. Any view function shared between a route and a Searcher
  must guard `if(page.options)`.
- **Wrap the body in try/catch.** It is a shared page; a throwing Searcher damages
  everyone's results. qobuz is the only plugin that guards this.
- One Searcher emits one section — dailymotion needs two registrations for users and
  videos.

## HTTP

The wrapper is thin; the semantics are in `es_io.c`. `[CORE]` `movian/http.js:93-104`:
passing a third argument makes the call **async with an error-first callback**
`function(err, res)`; omitting it makes the call **synchronous and throwing**.

### Building the request, and reading the reply

`[CORE]` The fields that *build* the request, all read in `es_io.c:303-410` (the cache
and failure fields are covered by the rules below):

| field | line | effect |
|---|---|---|
| `args` | `:394` | **query string**, escaped by the core. An object, or an array of objects merged left to right |
| `headers` | `:319` | request headers |
| `postdata` | `:341` | buffer, or object (form-encoded), or string |
| `method` | `:404` | verb; defaults to GET, or POST when `postdata` is set |
| `compression` | `:307` | sends `Accept-Encoding: gzip` — `[6/9]`, set it |
| `noFollow` | `:306` | do not follow redirects (how you read a `Set-Cookie` off a 302) |
| `verifySSL` | `:310` | verify certificates |
| `headRequest` | `:312` | HEAD |
| `noAuth` | `:308` | skip auth — **also skips your inspectors** |
| `debug` | `:305` | log the exchange |

`args` is what a REST API needs and it is easy to miss: build query strings with it, not
by string concatenation, or you will escape wrong.

The reply carries `res.statuscode`, `res.buffer`, `res.responseheaders`. **Get the body
with `res.toString()`** — `movian/http.js`'s `HttpResponse` also offers `bytes`,
`headers_lc`, `contenttype` and `convertFromEncoding(charset)` for sources that are not
UTF-8.

**1. Use the async form. Reserve synchronous requests for start-up.** A sync request
blocks the Duktape context; m7-jellyfin and soap4.me block on every page load.

**2. Set `noFail: true`.** `[5/9]` `[CORE]` `es_io.c:309` → `FA_CONTENT_ON_ERROR`.
Without it an API's own error body is unreachable, and the message you show the user
becomes "HTTP 400".

**401 is the one status that has not always honoured it.** In this core it does —
`fa_http.c:3206-3211` returns the body when `FA_CONTENT_ON_ERROR` is set, ahead of the
authentication path. On older cores 401 went to `authenticate()` regardless, which is
what qobuz's `lib/qobuz.js:85-90` records. Either way, a 401 is a signal to fix
credentials in an inspector, not something to parse out of a body — and note that
`noAuth` skips your inspectors along with the auth.

**3. Then check `statuscode` — and exempt `0` *and* `304`.** `[CORE]` A cache hit does
not arrive as 200, and it arrives two different ways:

- **`0` — fresh from the blob cache.** `fileaccess.c:1621` sets the protocol code to 0
  and the fresh-from-cache early return never assigns it, so the response arrives with
  `statuscode === 0` and `err === null`. Three independent authors found this without
  documentation — the strongest convergence in the corpus, and it is convergence on
  working around a defect.
- **`304` — a cached entry the core revalidated.** `fileaccess.c:1701-1709` returns the
  **cached body** while `fa_http.c:3187` has already put 304 in the protocol code, which
  `es_io.c:243` passes straight through as `res.statuscode`. So you get a complete,
  correct body under a status every naive check rejects.

Accept the endpoint's whole success contract, not just 200 — a POST that answers 201 or
a ranged request that answers 206 is not a failure:

```js
if(err) return cb(err);
var ok = (res.statuscode >= 200 && res.statuscode < 300) ||
         res.statuscode === 0 || res.statuscode === 304;
if(!ok) return cb('HTTP ' + res.statuscode);
```

The 304 case is not theoretical. A plugin that exempts only `0` works on first run and
shows an error page on the second, once the entry is old enough for the core to
revalidate rather than serve outright — observed while building a plugin from this
canon, in both directions. **`[0/9]`** handle it: the literal `304` appears in no `.js`
or `.ts` file of any of the nine, excluding `node_modules/`, `dist/`, `build*/`,
`releases/` and `tests/`. That search would not have seen a check written as a range
(`>= 400`, `< 300`), which would handle the case without naming it.

**4. To cache, pass `cacheTime`. Do not rely on `caching` alone.** It is not inert —
youtube and dailymotion cache successfully with it, because neither sets a request
header. It is *conditional*, and the conditions are invisible: `[CORE]` `es_io.c:414-415`:
when `cacheTime` is 0, `caching: true` is silently vetoed by **any** request header whose
name is not `user-agent` — `Accept` is enough. And even if it survives, `fileaccess.c:1742`
stores nothing unless the origin permitted it. `cacheTime: N` (`es_io.c:313`) skips the
veto and forces a minimum lifetime even against `Cache-Control: no-store`
(`fileaccess.c:1741`).

The naming is backwards from the behaviour: `cacheTime` is the switch, `caching` is a
request the core may decline. Measured: **five of nine set a cache flag at all, and two
of those found the deterministic spelling.**
trakt sets `caching: true` four times, comments that it caches, and does not cache —
three unconditional headers veto it. tmdb tried it and commented it out, probably
because its `Accept` header made it do nothing.

```js
opts.caching = true;
opts.cacheTime = CACHE_CATALOG;   // named per-endpoint TTLs, e.g. 120
```

**5. Never cache an authenticated or per-user endpoint.** `[CORE]`
`fileaccess.c:1658-1659` keys on the URL alone — not headers, not cookies, not
`Authorization`, not method. qobuz's total abstention is the model.

**6. A cached 200 is not a valid 200.** `[CORE]` `fileaccess.c:1742` stores anything
under 300, including anti-bot interstitials and login walls. If your source can serve
those, validate the *body* and re-issue bypassing the cache.

**Bypassing means deleting `cacheTime`, not setting `caching: false`.** `[CORE]`
`es_io.c:314` is `ehr_cache = es_prop_is_true("caching") || ehr_min_expire` — a non-zero
`cacheTime` turns caching back on by itself, so a retry that flips only `caching` is
served the same poisoned entry:

```js
var retry = {};
for(var k in opts) retry[k] = opts[k];
delete retry.cacheTime;               // deleting this is what disables the cache
retry.caching = false;
```

**7. The API cache caches bytes, not meaning.** It only caches GET with no body
(`es_io.c:163-166`), so POST results are structurally uncacheable, and a hit still costs
you the full parse. Add your own TTL map for parsed objects and for anything keyed by a
domain identity rather than a URL. A ~110-line factory with expire-on-read and size
eviction is enough.

**8. Return cache provenance to your callers.** `[2/9]` UI pacing depends on it — see
the `haveMore` delay above.

**9. Back off on 429.** One plugin in nine implements a backoff (trakt, additive on the
device-code poll); one more names 429 in an error message without backing off (qobuz);
the remaining seven ignore it.

### Inspectors — auth, and headers the player needs

`io.httpInspectorCreate(pattern, callback, async)` is on `native/io`, not on
`movian/http`. `[5/9]` — five plugins register one (youtube, trakt, HDRezka, anilibria,
qobuz), four of them reaching past the documented module to find it, for OAuth 401s,
anti-bot cookies and Cloudflare impersonation.

Use it for anything that must reach requests **you do not make** — the media URLs the
player opens directly never pass through your `http.request` calls.

**The two modes have different protocols. Do not mix them.** `[CORE]`

| mode | third arg | how you signal |
|---|---|---|
| sync | `false` / omitted | **`return 0`** means "I did nothing"; anything else means "handled" (`es_io.c:796-801`) |
| async | `true` | **`ctrl.proceed()` / `ctrl.fail()`** (`es_io.c:635-645`) |

`proceed()` **does nothing in sync mode.** `[AUTHOR]` youtube is the only plugin that
uses both modes, and gets both right. trakt gets async right (`src/api.js:43` passes
`true`, and every branch ends in `ctrl.proceed()` or `ctrl.ignore()`). Two of the three
sync users — HDRezka (`utils/httpInspector.js:142`, `:222`) and qobuz
(`lib/inspector.js:71`, `:97`) — call `proceed()` synchronously, where it is a no-op, and
work only by accident: falling off the end returns `undefined`, which coerces to the same
verdict as `return 0`. `[2/9]` anilibria (`lib/transport.js:22-34`) calls neither and is
accidentally correct. **No plugin in the corpus signals sync mode deliberately except
youtube's own `return 0` (`youtube.js:50`).**

**Credentials belong on the 401, not on a login button.** `[AUTHOR]` youtube puts the
entire device flow inside an async inspector gated on `ctrl.authFailed`, and resumes the
request that triggered it with `proceed()` rather than re-issuing. `authFailed` and async
mode landed in the same core commit — the feature exists for this shape.

trakt, whose `src/auth.js` is a near-verbatim descendant of youtube's `api.js`, kept the
mechanism as well as the popup: `src/api.js:11-43` is the same async-inspector shape,
refreshing the token and falling back to device login on `ctrl.authFailed`. `[COPIED]`
Its `settings.createAction("login", ...)` button (`trakt.js:57-59`) is a *second* entry
point for switching accounts, not the primary auth path — which is the right way to
offer one. Do the same: inspector first, button as an extra.

Do not set `noAuth` on a request you want an inspector to see.

## Settings

**Prefer `page.options` over a global settings page.** `[CORE]` `page.js:197-199` backs
`page.options` with `kvstoreSettings` keyed on **the page's URL**, so a choice persists
for that page and not globally. `[AUTHOR]` youtube is the only plugin of the nine with no
global settings page at all, using `page.options.createMultiOpt(...)` for sort order and
duration filter instead.

The strongly-supported claim is *"a plugin does not need a settings page to be
complete"*; three other plugins found `page.options` independently. A global settings
page is right for credentials and for anything that is not about one page.

## Checking a claim before you act on it

This corpus has produced wrong findings repeatedly, always the same two ways.

- **Take identifiers from the source that consumes them.** Grepping `cachetime` for
  `cacheTime` produced "no plugin uses the HTTP cache"; the truth is six of nine.
- **A claim of absence names its search surface and what it could not have seen.**
  `page.metadata.logo` was declared to have no consumer by a search over `glwskins/` and
  rendering code — it is read in `navigator.c` under `#if ENABLE_BOOKMARKS`.
- Plain `grep -r` under-reports on these repos — it returned nothing for a plugin that a
  `find`-driven traversal found two hits in. Use a real exclusion expression, or an
  author's intent gets counted twice out of a bundle:

  ```sh
  find <repo> \( -name node_modules -o -name .git -o -name .codegraph \
    -o -name dist -o -name 'build*' -o -name releases -o -name tests \) -prune \
    -o -type f \( -name '*.js' -o -name '*.ts' \) -print0 | xargs -0 grep -n '<pattern>'
  ```
- **Before "N plugins agree", check whether the N share a lineage.** `[COPIED]`

Use codegraph before grep — **eight of the nine plugins are indexed; `soap4.me` is not**,
and must be read directly.

## Where the type system stops seeing

Invented members are caught where you write them — `Item.onSelect`, `Page.searchable`,
`DB.row`, `popup.web` are all errors at the line. **But only where the object carries a
type.** Two escapes, both measured:

**1. A handler parameter that nothing types.** Covered above: annotate every route and
Searcher handler you do not write inline as the `new page.Route(...)` argument.

**2. An element of a returned array.**

```js
doc.root.getAttribute('href');                                // caught
doc.root.getElementsByTagName('a')[0].getAttribute('href');   // silent
```

A method returning an **array** of a known shape is emitted as `any`, so everything
reached through its elements is unchecked. Core issue #179.

Assigning the element to a plain local does **not** fix it — a local inferred from an
`any` expression is itself `any`. The annotation is what restores checking:

```js
var el = doc.root.getElementsByTagName('a')[0];
el.getAttribte('href');            // silent

/** @type {import('movian/html').Node} */
var el2 = doc.root.getElementsByTagName('a')[0];
el2.getAttribte('href');           // TS2339
```

Annotate, or check that call by running it.

## What this skill does not cover

| question | go to |
|---|---|
| what exists, what its signature is | `movian:api` and the generated `.d.ts` |
| where a file belongs, manifest fields | `movian:shape` |
| launching, opening a route, screenshots, logs | `movian:run` |
| whether a result proves anything | `movian:verify` |
| `.view` files, GLW layout and focus | `movian:view` |
| finding the core checkout | `movian:locate` |
