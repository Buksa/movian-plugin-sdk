---
name: api
description: Find the authoritative Movian plugin API surface — module list, signatures, manifest fields, runtime model — without guessing. Use when writing or reviewing plugin JS, when unsure whether a function or module exists, when checking what a require() path provides, when setting up type checking for a plugin, or when a plugin calls something that may not exist in this core.
---

# The Movian plugin API, authoritatively

**Do not answer API questions from memory.** Movian is a fork; other forks
implement builtins this one does not, and the difference shows up as a plugin
that loads fine and then renders `Unknown function` in the UI. Check the
artifacts.

Everything below lives in the core checkout, reached through `$(mdev core)` — see
`movian:locate` if that fails. It is deliberately *not* copied into this skill:
it describes core code and must not drift from it.

## The three sources, in order of authority

**1. Generated types — `$(mdev core)/generated/movian-api.d.ts`**

Emitted by `support/devtools/metadata/gen.py` from the core sources, so it cannot
disagree with the runtime about *what exists*. 38 declared modules:

```
fs  http  https  querystring  url  websocket
movian/html  movian/http  movian/itemhook  movian/page  movian/popup
movian/prop  movian/service  movian/settings  movian/sqlite  movian/store
movian/subtitles  movian/videoscrobbler  movian/xml  movian/xmlrpc
native/crypto  native/faprovider  native/fs  native/gumbo  native/hook
native/htsmsg  native/io  native/kvstore  native/metadata  native/misc
native/popup  native/prop  native/route  native/service  native/sqlite
native/string  native/subtitle  native/websocket
```

Use it to answer "does this module/export exist" definitively. Its **signatures
are weak** — many members are typed `any` — so it settles existence, not shape.

Verify it is current before trusting it:

```
(cd "$(mdev core)" && python3 support/devtools/metadata/gen.py --check)
```

**2. Prose reference — `$(mdev core)/docs/Guides/PLUGIN_API_REFERENCE.md`**

814 lines: runtime model, plugin manifest, globals, the public CommonJS modules,
node-style compatibility shims, the legacy v1 API, native modules, and
Duktape-specific behaviour. This is where semantics live — what a call *does*,
not merely that it exists. Hand-written, so where it disagrees with the generated
types about existence, the types win.

Alongside it: `PLUGIN_DEVELOPMENT_NOTES.md`, `PLUGIN_DEBUG_WORKFLOW.md`, and
`PLUGIN_FS_SECURITY_AUDIT.md` (the filesystem ACL that confines a plugin's `fs`
reads to its own directory — relevant whenever a plugin reads outside itself).

**3. Runnable examples — `$(mdev core)/plugin_examples/`**

Eight small working plugins: `async_page_load`, `itemhook`, `listx_cloner`,
`music`, `settings`, `subscriptions`, `videoscrobbling`, `webpopupplugin`. When
the question is "what does the idiomatic call sequence look like", these beat
prose.

## The language constraint that catches people

Plugin JS runs on **Duktape at ES5.1**. No `let`/`const`, no arrow functions, no
template literals, no `Promise`, no destructuring. The generated header says so
in its first lines. Code that looks fine in review will fail at parse time in the
app, so check syntax level before blaming logic.

## Type checking a plugin

Point the plugin's `tsconfig.json` at the generated bundle so `tsc --noEmit`
resolves Movian modules instead of erroring on every `require()`. Because the
declarations are `any`-heavy, this catches **wrong module and wrong member**
names, not wrong argument types — still the cheapest real bug filter available
for a Movian plugin.

## Gotchas that cost people time

`references/plugin-gotchas.md` — the HTML parser's singular-vs-plural
`getElement*` naming (and a compatibility wrapper for older Movian builds), and
horizontal rows with `list_x`.

## When the API surface itself is wrong or missing

Improving the generated types and the reference is the **core repo's** work, not
a plugin repo's. File it there. From a plugin repo, work around it and note it.
