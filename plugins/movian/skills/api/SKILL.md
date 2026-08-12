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

Twenty small working plugins, all of which the core compiles on every run
(movian#175). Eight at the top level — `async_page_load`, `itemhook`,
`listx_cloner`, `music`, `settings`, `subscriptions`, `videoscrobbling`,
`webpopupplugin` — plus twelve graded ones under `01-basic/`, `02-intermediate/`
and `03-advanced/`, from `01-hello-world` to `02-oauth-authentication`. When the
question is "what does the idiomatic call sequence look like", these beat prose.

## The language constraint that catches people

Plugin JS runs on **Duktape at ES5.1**. No `let`/`const`, no arrow functions, no
template literals, no `Promise`, no destructuring. The generated header says so
in its first lines. Code that looks fine in review will fail at parse time in the
app, so check syntax level before blaming logic.

## Type checking a plugin

```
mdev types                    # symlink the bundle into ./types/
echo 'types/movian-api.d.ts' >> .gitignore
```

Then include `types/**/*.d.ts` in `tsconfig.json`. Never put the core's absolute
path in a committed `tsconfig` — `mdev types` exists so the config can name a
stable relative path. `mdev types --copy` vendors a snapshot instead, for a repo
that must typecheck without a core checkout.

Measured on `movian-plugin-trakt`: `tsc` could not resolve a single Movian
module before, and resolves all of them after.

### A green `tsc` is a claim, and `mdev types` now checks it

The symlink tracks the core, but **the core itself can be old**, and then the
declarations you compile against are permanently behind the ones that do the
checking. This is not hypothetical (movian#183): a session built a plugin against
a checkout that predated movian#171, #172, #176 and #178, got a clean `tsc`, and
every one of

```js
page.searchable = true;   item.onSelect = f;   page.appendItm(...)
```

passed — the three defects the core had just been changed to catch. Nothing in
the checkout dissented: `gen.py --check` was green, and so were all six of `mdev
lsp doctor`'s checks. They ask the checkout about itself, and a merely-old
checkout answers all of them correctly.

So `mdev types` compiles a probe that is **wrong on purpose** against the file it
just handed you, and reports whether the artifact says so:

```
typefloor: OK -- 3 planted defects all reported (tsc Version 5.7.3)
```

If instead it prints `FAILED`, the artifact is not checking your plugin, and a
green run against it means nothing. Read which core you are on
(`mdev doctor` prints the branch and how far behind), then regenerate or repoint.
`mdev doctor` runs the same check. `--no-verify` skips it; there is deliberately
no quiet fallback, because "could not check" must not read like "checked, fine".

**Three limits worth knowing before you trust a result:**

1. **`any`-heavy.** This catches wrong *module* and wrong *member* names, not
   wrong argument types.
2. **No `showtime/*` modules are declared**, yet they work — the core rewrites
   `showtime/X` to `movian/X` at require time (`src/ecmascript/ecmascript.c:436-440`).
   A legacy-style plugin will show false `Cannot find module` errors for them.
3. **Modules mutate their own exports at runtime.** `movian/settings` statically
   exports only `globalSettings` and `kvstoreSettings`, but
   `settings.globalSettings(...)` called *as a method* sets `this.__proto__` on
   the module object, after which `settings.createBool` and friends exist. So a
   member the bundle does not declare is not proof of a bug — read the module
   source before calling it one.

If the plugin already has hand-written declarations for the same modules, **do
not add the bundle alongside them**: ambient declarations of the same module name
merge, and duplicate members become `TS2451 Cannot redeclare`. Measured on
HDRezka: 28 errors became 61, forty of them redeclarations.

## Gotchas that cost people time

`references/plugin-gotchas.md` — the HTML parser's singular-vs-plural
`getElement*` naming (and a compatibility wrapper for older Movian builds), and
horizontal rows with `list_x`.

## When the API surface itself is wrong or missing

Improving the generated types and the reference is the **core repo's** work, not
a plugin repo's. File it there. From a plugin repo, work around it and note it.
