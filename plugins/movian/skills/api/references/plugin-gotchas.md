# Plugin gotchas

Moved from the core repo's `docs/Guides/PLUGIN_DEVELOPMENT_NOTES.md`; its
"Developer Guide Roadmap" section stayed there, being core planning.

These notes collect small compatibility rules for Movian plugin development.
They are intentionally narrow for now and can grow into a fuller developer
guide together with more complete `plugin_examples/` coverage.

## HTML Parser Naming Compatibility

Plugins can parse HTML through:

```js
var html = require('movian/html');
var doc = html.parse(source);
```

The current long-standing API exposes these node methods:

- `getElementById(id)` returns one node or `null`.
- `getElementByClassName(className)` returns an array.
- `getElementByTagName(tagName)` returns an array.

The class and tag helpers return multiple nodes, even though their historical
names use singular `Element`. Movian also provides DOM-style plural aliases:

- `getElementsByClassName(className)`
- `getElementsByTagName(tagName)`

For plugins that should also run on older Movian builds, prefer a small
compatibility wrapper instead of copying the whole built-in HTML module.

Example `utils/html_compat.js`:

```js
var html = require('movian/html');

function patchNode(node) {
  if (!node)
    return node;

  var proto = node.__proto__ ||
    (Object.getPrototypeOf ? Object.getPrototypeOf(node) : null);

  if (!proto)
    return node;

  if (!proto.getElementsByClassName && proto.getElementByClassName)
    proto.getElementsByClassName = proto.getElementByClassName;

  if (!proto.getElementsByTagName && proto.getElementByTagName)
    proto.getElementsByTagName = proto.getElementByTagName;

  return node;
}

exports.parse = function(source) {
  var doc = html.parse(source);
  patchNode(doc.document);
  patchNode(doc.root);
  return doc;
};
```

Plugin code can then use the plural names consistently:

```js
var html = require('./utils/html_compat');

var doc = html.parse(body);
var items = doc.root.getElementsByClassName('item');
var links = doc.root.getElementsByTagName('a');
```

This keeps compatibility local to the plugin while leaving the built-in module
as the source of truth for parser behavior.

## Horizontal Rows With `list_x`

Plugins can build pages with any number of independently scrollable rows. Add
each row as a passive page item whose `data` contains that row's cards:

```js
page.appendPassiveItem('list', upcomingCards, {
  title: 'Movies - Upcoming'
});
page.appendPassiveItem('list', nowPlayingCards, {
  title: 'Movies - Now Playing'
});
page.appendPassiveItem('list', topRatedCards, {
  title: 'Movies - Top Rated'
});
```

The outer cloner creates the sections. Each section then clones its own
`$self.data` into a separate `list_x`:

```view
widget(list_y, {
  cloner($self.model.nodes, container_y, {
    widget(label, {
      caption: $self.metadata.title;
    });

    widget(list_x, {
      id: "section-row";
      focusable: 1;
      chaseFocus: 0;
      navWrap: false;

      cloner($self.data, loader, {
        source: "skin://items/rect/default.view";
      });
    });

    widget(slider_x, {
      bind("section-row");
      focusable: canScroll();
      alpha: iir(canScroll(), 16);
    });
  });
});
```

Keep the optional scrollbar inside the same cloned section as its row. The
local `"section-row"` ID then binds to that section's `list_x`, so every row
keeps an independent scroll position.

Keyboard and D-pad navigation continue to use left/right focus movement. Touch
or simulated touch can drag the row horizontally, while a vertical swipe over
a card continues to scroll the outer `list_y`. On Linux/WSL this can be tested
with `--pointer-is-touch`.

A complete runnable implementation is available in
`plugin_examples/listx_cloner`.

## The Rest Below Was Found Building SmartTwitchTV

Citations are to the core at `movian6` @ `0faa94a0d`; run evidence is the
SmartTwitchTV plugin's git history.

## `movian/store` Writes Five Seconds Late

A store's setter only arms a timer; the file is written 5 s after the last
change (`res/ecmascript/modules/movian/store.js:16-23`). There is a finalizer
that writes a pending change (`store.js:41-46`), but quitting Movian within 5 s
of a change lost it in a run: SmartTwitchTV stored a rotated Twitch refresh
token, the old one was already invalid, and the next start logged the user out
(SmartTwitchTV `540fa15`).

For a value that must survive a quit, also write the same file at once. The
store file is `Core.storagePath + '/store/' + name` (`store.js:59`) holding
`JSON.stringify` of all keys (`store.js:21`), so write every key the store
holds, not only the changed one:

```js
var fs = require('fs');
var store = require('movian/store').create('account');
var storeFile = Core.storagePath + '/store/account';

function save(session) {
  store.session = session;
  fs.writeFileSync(storeFile, JSON.stringify({clientId: store.clientId, session: session}));
}
```

## Set Up the Page Before the First Network Call

In a route, set `page.type`, `page.loading = true` and
`page.metadata.glwview` before fetching anything. `Route` does neither for you
(`res/ecmascript/modules/movian/page.js:453-467`).

- Fetching first and setting up the page after left a paginated grid that
  never asked for its second page, stopping at 24 items (SmartTwitchTV
  `3353f26`; observed, the mechanism was not traced in the core).
- `mdev open` takes an absent `loading` that stays absent for 1 s as a
  finished static page (`support/devtools/mdevlib/harness.py:1469-1503`,
  `ABSENT_LOADING_SETTLE` at `:105`). A route still in its first request then
  reports ready with 0 nodes.

## Language: `global.i18n.iso639_1` Is Not ISO 639-1

The core sets it to the first two letters of the chosen catalog's file name
(`src/i18n.c:550-553`), not to a real language code. Catalog names in `lang/`
include `sp_SP.lang`, `ua_UA.lang` and `dk_DK.lang`, so Spanish reads `sp`,
Ukrainian `ua` and Danish `dk`. Map those yourself if you need real codes.

Read it when you need it, never at module load. Dev plugins load in
`plugins_init()` (`src/main.c:507`) and installed ones in the `swinst` thread
started at `src/main.c:517`; `i18n_init()` runs after both, at
`src/main.c:520`. At load time the value is unset or racing.

Plugin JS gets no translation API, and GLW `_("...")` looks the string up in
the core catalog only (`src/ui/glw/glw_view_parser.c:568-573`,
`nls_get_prop()` at `src/i18n.c:384`). A plugin that wants its own
translations ships its own tables and passes the strings to its views, e.g. as
a `page.metadata` subtree (next section). A worked design:
SmartTwitchTV `docs/i18n.md`.

## Assigning an Object to `page.metadata` Makes a Prop Subtree

`page.metadata.x = {a: 1, b: 2}` does not store an object: the prop proxy's
setter creates child props and assigns each key
(`res/ecmascript/modules/movian/prop.js:33-56`). A view reads them as
`$self.model.metadata.x.a`. Assigning again merges keys into the existing
subtree; keys missing from the new object are not removed.

Inside an item cloner `$self` is the item, so reach the page through
`$parent.model.metadata.x.a`: a clone's `$parent` is the `$self` of the scope
the cloner was written in (`src/ui/glw/glw_view_eval.c:1446-1452`). In a
cloner nested inside another cloner, that is the outer item, not the page.

## Plugin `fs` Paths

Plugin file access is refused with "Access not allowed" unless the path starts
with the plugin's own `Plugin.path` or its `Core.storagePath`
(`src/ecmascript/es_fs.c:84-108`). The manifest's
`entitlements.bypassFileACLRead` / `bypassFileACLWrite` lift the check
(`src/plugins.c:718-724`), and so does `--bypass-ecmascript-acl`, which
`mdev preview` always passes, so a preview proves nothing about the ACL.

Reading the plugin's own files works from an installed zip too, where
`Plugin.path` is a `zip://` URL: `fs.readFileSync(Plugin.path + 'lang/ru.lang')`
(SmartTwitchTV `i18n.js`).

## Hand-Placed Installed Zips Need `<id>@<origin>.zip`

Movian reads the origin from the part of the file name after `@` in
`<persistent>/mrp/installed/` (`src/plugins.c:810-838`). A zip named without
`@` passes a NULL origin to `plugin_make()`, whose `strdup(origin)`
(`src/plugins.c:248`) crashes Movian at every start until the file is removed
(Buksa/movian#297). The
repository installer always writes the right name; this bites tests and
side-loading only.
