# Repo shape and build across the nine plugins

Research for [issue #20](https://github.com/Buksa/movian-plugin-sdk/issues/20),
part of the [plugin authoring canon](https://github.com/Buksa/movian-plugin-sdk/issues/19).
Investigated 2026-08-06.

**Sources.** Three kinds, marked throughout:

- **[READ]** — the plugin checkouts on this machine, read-only. Cited `path:line`.
- **[CORE]** — `/home/uzver/movian-public-clean` (`src/plugins.c`,
  `src/ecmascript/ecmascript.c`), and the core commit `5706c66cf` in the
  `zCode-smb2-client-parity` worktree.
- **[MEASURED]** — experiments run locally in a scratchpad. Two of them: every
  shipped `.js` in the corpus parsed by `acorn` with `ecmaVersion: 5` (a real
  ES5.1 parser), and m7-jellyfin's `.swcrc` fed to `@swc/core` 1.15.43 to see
  what it actually emits. Nothing was written into any plugin repo.

Inferences are labelled **[INFER]**. Where a plugin contradicts the generalisation,
it is called out rather than smoothed.

---

## 0. The headline answer

**The ticket's premise is wrong in one specific and load-bearing way: there are not
four transpiling plugins, there are three.** HDRezka's swc is a *minifier*, not a
compiler — and the distinction is exactly the one the canon needs, because it
separates "I write modern JS and compile down" from "I write ES5 and squeeze it".

Measured, not asserted: all 68 shipped HDRezka `.js` files parse clean as ES5.1.
So do trakt's 13, anilibria's 9, youtube's 14, qobuz's 4 and tmdb's 1. Only
m7-jellyfin's `src/` (10 of 11 files fail) and soap4.me's `src/index.js` do not,
and dailymotion ships `.ts`. **Six of nine write ES5 by hand; three transpile.**

What the transpile buys, per the three that do it, is not one thing:

| plugin | what the build actually buys |
|---|---|
| m7-jellyfin | modern *syntax* — `class`, `??`, template literals, default params |
| soap4.me | ES2015 *modules* (`import`) + syntax |
| dailymotion | *types* — the `.ts` is ES5-shaped `var` code with annotations |

What it costs is uniform and severe: **all three cannot be loaded by Movian as
checked out.** `dist/`, `out/` and the emitted `dailymotion.js` are absent from
every working tree (§4). jellyfin has no committed `plugin.json` at all. A reader
of any of these three repos cannot run what they are reading.

And the second cost is the one core commit `5706c66cf` already paid for: a
compiler configured to *emit* ES5 will happily accept ES6 and downlevel it, so it
never tells you your source is out of the runtime's reach. It removes the error
instead of reporting it (§6).

**A correction to the map.** `JSON.parse(Plugin.manifest)` is not "an idiom no
other plugin has". It is in **five of nine** — the single strongest convergence in
the corpus (§5).

---

## 1. Per-plugin shape

Entry point resolution is the same everywhere and comes from the core:
`plugins.c:619` reads `<url>/plugin.json`, `plugins.c:704` takes the `file` field,
and `plugins.c:710` joins it to the plugin root. So "where the entry sits" is
always *relative to the directory holding `plugin.json`*. [CORE]

| plugin | entry (as Movian sees it) | sources | build | `plugin.json` | tree is loadable as checked out |
|---|---|---|---|---|---|
| HDRezka | `HDRezka.js` (root) | 8 sibling dirs | optional minify/bundle | committed | **yes** |
| trakt | `trakt.js` (root) | `src/` (12 files) | none | committed | **yes** |
| anilibria | `anilibria.js` (root) | `lib/` (8 files) | none | committed | **yes** |
| youtube | `youtube.js` (root) | `support/`, `ytdl-core/` | none | committed | **yes** |
| qobuz | `qobuz.js` (root) | `lib/` (3 files) | none | committed | **yes** |
| tmdb | `tmdb.js` (root) | none — one 2858-line file | none | committed | **yes** |
| m7-jellyfin | `jellyfin.js` at *zip* root | `src/` (11 files) | swc + node | **generated** | **no** |
| soap4.me | `index.js` at *out/* root | `src/index.js` | Babel + gulp | **generated** | **no** |
| dailymotion | `dailymotion.js` (root, gitignored) | `src/ts/` | `tsc` | committed | **no** |

### The six without a build

`HDRezka.js`, `trakt.js`, `anilibria.js`, `youtube.js`, `qobuz.js`, `tmdb.js` each
sit at the repo root beside `plugin.json`, and pull siblings with relative
`require`. trakt: `trakt.js:27-30` requires `./src/api`, `./src/auth`,
`./src/log`, `./src/lookup`. qobuz: `qobuz.js:14-16` requires `lib/qobuz`,
`lib/inspector`, `lib/bundle`. [READ]

Three of the six carry a `tsconfig.json`, and in **all three it is
`"noEmit": true`** — type-checking only, no output:
`movian-plugin-HDRezka/tsconfig.json:9`, `movian-plugin-trakt/tsconfig.json:9`,
and jellyfin's equivalent `m7-jellyfin/jsconfig.json:6`. [READ] A `tsconfig.json`
in this corpus is **not** evidence of a build step. That is the trap that produced
the ticket's "four transpilers" count.

tmdb is the outlier on two axes: it has no `.git` directory at all on this machine
(so nothing is "committed" in any checkable sense), and its `plugin.json` has **no
`apiversion` key**. `plugins.c:712` defaults a missing `apiversion` to `1`, which
is precisely why tmdb reaches the API through the global `showtime.*` and never
calls `require` — the parent map's style table has a causal explanation, not just
a correlation. [CORE] [READ] Every other plugin declares `"apiversion": 2`. [READ]

### HDRezka — a minifier, not a compiler

`package.json:5-8` defines two scripts, `build:js` → `scripts/minify-swc.js` and
`build:js:bundle` → `scripts/bundle-swc.js`. [READ] The first calls
`swc.minify(code, {ecma: 5, module: false, compress, mangle})`
(`scripts/minify-swc.js:45-51`) — `swc.minify`, not `swc.transform`, and `ecma: 5`
on input that is already ES5. Its own header says so: *"Each .js is minified in
place preserving the original directory layout"* (`scripts/minify-swc.js:2-3`).
[READ]

The release driver `scripts/build.sh:11` defaults `JS_MODE=min` and offers
`--source`, which *"Ship original .js verbatim (debug)"* (`build.sh:132`) and zips
the repo's own files unchanged (`build.sh:157-164`). A mode that ships the source
verbatim is only possible because the source is already runnable. [READ]

`build.sh` also does release chores no other plugin does: it refuses a dirty tree
(`:46-49`), syncs `repo.json`'s version to `plugin.json`'s (`:57-71`), and fails
if `CHANGELOG.md` lacks a heading for the version (`:78-82`). [READ]

The author recorded an A/B measurement in the comments — bundle mode is *"+45-55%
memory overhead vs source (one compiled closure)"* (`build.sh:8-10`), with the
reasoning that per-file modules let Duktape free each factory's source after it
runs (`minify-swc.js:6-12`), and that the bundle is *"~15% smaller than esbuild's
own minify (109 KB vs 129 KB)"* (`bundle-swc.js:15`). These are **the author's
numbers, quoted, not reproduced here.** [READ]

Two drift notes: `build.sh:158` copies `semiauto_updater.js`, which does not exist
in the tree; and the four build output dirs are all gitignored
(`.gitignore:1-5`: `dist/`, `build/`, `build-min/`, `build-swc/`). [READ]

---

## 2. The three real builds

### m7-jellyfin — swc, and no committed manifest

`package.json:19`: `"build": "swc src -d dist && node ./bin/build.js"`. [READ]
The `.swcrc` sets `module.type: commonjs` and `jsc.parser.syntax: ecmascript`, and
**does not set `jsc.target`** (`.swcrc:1-19`). [READ]

**[MEASURED]** Fed that exact `.swcrc` to `@swc/core` 1.15.43 with a probe
containing a `class`, a default parameter, a template literal, `??` and object
spread: the output has none of them — `class` becomes a `/*#__PURE__*/` IIFE with
`Object.defineProperty` accessors, the template literal becomes `"v".concat(...)`.
Setting `jsc.target: "es5"` explicitly produced byte-identical output; setting
`"es2022"` preserved all five constructs. So swc's default target here **is** ES5,
and the omission in `.swcrc` is harmless. The same run also showed `jsc.minify`
being applied (identifiers mangled) without any top-level `minify: true`, so
jellyfin's `dist/` is downlevelled *and* minified. `node_modules` is absent from
the checkout, so this used HDRezka's installed copy of swc; jellyfin pins
`^1.15.10` (`package.json:24-25`), and I could not measure its own resolved
version — **[INFER]** that a 1.15.x patch difference does not change the default
target.

The source genuinely needs this. `src/jellyfin.js:16` is `class Jellyfin`,
`:17` a default parameter, `:35` `??`. **[MEASURED]** 10 of 11 files in `src/`
fail an ES5.1 parse; only `src/polyfill.js` passes, which is itself a hand-written
ES5 shim installing `Object.entries`/`Object.values` (`src/polyfill.js:1-30`) —
because downlevelling syntax does not supply missing *library* methods. That
polyfill is the load-bearing detail the canon should carry: **a transpiler fixes
syntax, never the standard library.**

`bin/build.js` is the manifest generator. There is **no `plugin.json` anywhere in
the repo** — verified by `find`. [READ] Instead:

- `bin/build.js:7-13` destructures `movian`, `version`, `description`, `author`,
  `main` out of `package.json`;
- `:23-31` merges them into one object, setting `file: main` (`package.json:15` is
  `"main": "jellyfin.js"`);
- `:128-136` reads every file in `locales/` (`en.json`, `it.json`) and assigns the
  result to `plugin.i18n`;
- `:145-150` appends the serialised object into the zip **as `plugin.json`**.

So jellyfin's manifest is a *build product* assembled from three sources
(`package.json`'s `movian` key at `:32-42`, npm metadata, and `locales/`), and the
i18n block never exists as a file. `.gitignore:1` ignores `dist/`. [READ]

`bin/build.js:139-143` archives `dist/src` at the zip root, plus `assets/` and
`views/` under their own prefixes — which is why `file: "jellyfin.js"` resolves
even though the source lives in `src/`. **[INFER]** `swc src -d dist` emits to
`dist/src/`, matching `CURRENT_PATH` at `:21`; I could not run it without
`node_modules`.

Two things do not work as written: `bin/build.js:15,70` reads a `.gitattributes`
for an export-ignore list, and no `.gitattributes` exists (`loadIgnoreFile` returns
`[]` on error, `:81-83`), so the ignore list is always empty; and `views/`
contains only `.gitkeep` — jellyfin ships **zero** GLW views despite the build
archiving that directory. [READ]

`bin/dev.js:9-11` is the whole dev loop: copy `dist/jellyfin.zip` to
`$HOME/.hts/showtime/installedplugins/jellyfin.zip`. [READ]

### soap4.me — Babel + gulp, and the same manifest-generation idea

`package.json:7`: `"build": "npm install && ./node_modules/.bin/gulp"`, with
`babel-preset-es2015`, `gulp-babel` and `gulp` 3 in devDependencies (`:26-35`).
`.babelrc:1-3` is `{"presets": ["es2015"]}`. [READ]

`gulpfile.babel.js` has three tasks (`:72` — `default` is `plugin`, `assets`,
`config`):

- **plugin** (`:21-30`) — Babel over `src/**/*.js`, then `rename` to `index.js`,
  into `./out`.
- **assets** (`:32-37`) — copies `assets/**/*.{png,jpg,gif,view}`.
- **config** (`:39-64`) — the manifest generator.

The `config` task is the one worth reading closely. `package.json:36-84` holds a
`movian` key whose values for `file`, `author`, `version`, `homepage` and
`description` are all literally **`null`** (`:46-50`). The gulp task collects
exactly the null-valued keys (`:49-55`) and fills each either from a predefined
map (`file` → `index.js`, `:45-47`) or from the *top-level* npm field of the same
name, then writes the merged object out as `plugin.json` (`:57-58`). [READ]
`null` is used as a declarative "inherit this from npm" marker. Nothing else in
the corpus does this.

`.gitignore:8-9` ignores `releases/` and `out/`. `release.sh:6-13` bumps the npm
version, rebuilds into `out/`, and zips it flat (`zip -r -X -j`) into
`releases/<version>/plugin.zip`. [READ]

**Convergence worth naming.** jellyfin and soap4.me — a 2016 frontend engineer and
a 2024+ author, no contact — independently decided that **the manifest lives in
`package.json` and `plugin.json` is generated**. Neither commits a `plugin.json`.
That is two of the three builders arriving at the same answer.

### dailymotion — TypeScript, and a Grunt that does not compile

`tsconfig.json:4` targets `es5`, `:5` `module: commonjs`, `:6` `moduleResolution:
classic`, `:8` `outDir: ""`, `:2` `compileOnSave: true`, `:14` `watch: true`, and
`:16` `exclude: []`. [READ]

There is **no `tsc` invocation checked in anywhere.** `package.json:1-8` has no
`scripts` block at all — only `grunt` and `grunt-contrib-compress` as
devDependencies. And `Gruntfile.js:5-20` configures exactly one task, `compress`,
which zips `dailymotion.js`, `support/**.js`, `icon.png`, `LICENSE` and
`plugin.json` into `releases/release_<version>.zip`, with the version read out of
`plugin.json` at `:2-3`. [READ] **Grunt packages; it never transpiles.** The
compile is driven entirely by `compileOnSave`/`watch` in the editor — a build step
that only exists inside somebody's IDE. That is the most fragile arrangement in
the corpus.

`.gitignore:6-7` excludes `dailymotion.js` and `support` — the emitted output.
Neither exists in the checkout. **[INFER]** with `outDir: ""`, no `rootDir`, and
sources under `src/ts/`, tsc infers the common root as `src/ts` and emits to the
repo root, giving `dailymotion.js` and `support/*.js` — which is exactly the file
list `Gruntfile.js:12-16` compresses and exactly what `.gitignore:6-7` names.
Three independent artefacts agree, but I did not run tsc.

Unlike jellyfin and soap4.me, dailymotion **does** commit its `plugin.json`
(14 lines, hand-maintained; `version` at `:7` must be kept in step with
`package.json:3` by hand — both currently read `1.0.7`). [READ]

**What the TypeScript buys here is not modern syntax.** `src/ts/support/model.ts`
is `interface ModelPagination` at `:6`, `interface ModelCallback` at `:28`, and
functions annotated `(channelId: string, filters: api.BaseFilters, ...)` at
`:38-62`. Across the nine `.ts` files, `var` outnumbers `let`/`const` heavily
(20 `var` lines in `support/playback.ts` alone), there is exactly one `class`
(`support/log.ts:28`) and one arrow type annotation (`support/model.ts:8`). [READ]
Strip the annotations and the `export` keywords and it is ES5. dailymotion pays a
compiler for **types and a module system**, not for syntax — which makes it the
closest thing in the corpus to what the SDK's `.d.ts` work now offers *without* a
build.

---

## 3. Vendored third-party code

Not a build step, but the same problem solved differently, and it belongs in the
committed-vs-generated ledger:

- trakt vendors `libs/events/` and `libs/torrent-name-parser/` **with their
  upstream `package.json`, `.travis.yml` and full test suites** committed — 34 of
  its 54 tracked files. `tsconfig.json:18` excludes `libs` from type-checking.
- youtube vendors `ytdl-core/lib/` (7 files) and `support/` (`sax.js`,
  `jstream.js`, `html-entities.js`, `path.js`). [READ]

**[MEASURED]** All of it parses as ES5.1 — vendoring here means "found a library
that already runs on Duktape", not "compiled one down".

A naming trap for anyone grepping: qobuz's `lib/bundle.js` is **not** a build
artefact. Its header (`lib/bundle.js:1-9`) says it extracts `app_id`/`app_secret`
from the live Qobuz web-player *bundle*, and `:8` states *"ES5.1 only (Duktape
1.8.0)"*. [READ]

---

## 4. Committed versus generated

| plugin | generated, gitignored | present in checkout? |
|---|---|---|
| HDRezka | `dist/`, `build/`, `build-min/`, `build-swc/` (`.gitignore:1-5`) | no — but `--source` mode makes them optional |
| m7-jellyfin | `dist/` **and `plugin.json` itself** (`.gitignore:1`) | no |
| soap4.me | `out/`, `releases/` (`.gitignore:8-9`) | no |
| dailymotion | `dailymotion.js`, `support/` (`.gitignore:6-7`) | no; `releases/*.zip` **are** committed (7 of them) |
| trakt | `types/movian-api.d.ts` (`.gitignore:1`) | n/a — a type artefact, not runtime |
| anilibria, qobuz, youtube, tmdb | nothing | n/a |

Verified by `ls`: `m7-jellyfin/dist`, `movian-soap4.me/out`,
`movian-plugin-dailymotion/dailymotion.js` and `.../support` are all absent. [READ]

dailymotion is the one that contradicts its own class: it is the only plugin in
the corpus that **commits release zips** (`releases/release_1.0.1.zip` through
`1.0.7.zip`) while ignoring the plain files that go into them. The distributable
is in git; the thing you'd read is not.

---

## 5. `JSON.parse(Plugin.manifest)` — the map's claim is wrong

`plugins.c:726-727` passes `buf_cstr(b)` — the **raw, undecoded bytes of
`plugin.json`** as loaded at `:619` — into `ecmascript_plugin_load`.
`ecmascript.c:899-900` pushes that string onto the plugin object as `manifest`,
and `:910` installs the object as the global `Plugin`. [CORE] So `Plugin.manifest`
is the manifest *text*, and every consumer must `JSON.parse` it. The core gives it
to every apiversion-2 plugin for free, with no `require`.

The map and the ticket both call this *"an idiom no other plugin has"*. Census of
the corpus:

| plugin | site |
|---|---|
| soap4.me | `src/index.js:10` — `const plugin = JSON.parse(Plugin.manifest);` |
| HDRezka | `constants.js:12` — `var manifest = JSON.parse(Plugin.manifest);` |
| trakt | `src/plugin.js:2` — `return JSON.parse(Plugin.manifest);` |
| anilibria | `anilibria.js:16` — `var plugin = JSON.parse(Plugin.manifest);` |
| m7-jellyfin | `src/api.js:2`, and `src/jellyfin.js:83` passes `Plugin.manifest` into the constructor, which parses it at `:19-21` |

**Five of nine.** youtube, qobuz, dailymotion and tmdb do not use it. [READ]

Two corrections for the record: the line is `src/index.js:**10**`, not `:11`; and
soap4.me's distinction is not the idiom, it is **what it destructures** —
`:12-19` pulls `id`, `icon`, `i18n`, `title`, `category`, `synopsis` in one
statement and then uses `Plugin.path + icon` at `:21`. It treats the manifest as
the single source of identity. jellyfin does the same thing through getters
(`src/jellyfin.js:34-40`, `this.metadata.title ?? ''`). The convergence is
stronger than the map credits, and it is the strongest one in the corpus.

**Consequence for the canon.** Because jellyfin and soap4.me *generate*
`plugin.json` from `package.json` and *read it back* through `Plugin.manifest`,
`package.json` is the single source of truth for identity end-to-end. That is a
coherent, complete design that two authors reached independently, and it is
available to the six no-build plugins too — they already read the manifest, they
just hand-maintain the file.

---

## 6. What the transpile buys, and what it costs

**Buys — measured, and it is a different thing in each case:**

1. **jellyfin: syntax.** 10 of 11 `src/` files fail an ES5.1 parse. `class`,
   `??`, default parameters, template literals. Real, and the source would not
   load without swc. **[MEASURED]**
2. **soap4.me: modules.** `src/index.js:1-8` is eight ES2015 `import`
   statements. Babel turns them into the `require` calls Duktape needs. But note
   the shape it produces: gulp renames the Babel output to a **single**
   `index.js` (`gulpfile.babel.js:28`), and soap4.me has exactly one source file
   — so its module system buys nothing structurally that trakt's twelve-file
   `src/` + relative `require` does not already have without a compiler. [READ]
3. **dailymotion: types.** Not syntax — see §2. And this is the one the SDK's
   own `.d.ts` artefact now delivers with `noEmit: true`, which is exactly what
   HDRezka (`tsconfig.json:9`), trakt (`tsconfig.json:9`) and jellyfin
   (`jsconfig.json:6`) already do. **Three plugins get dailymotion's benefit
   without dailymotion's cost.**

**Costs — measured:**

1. **The repo stops being runnable.** All three build-dependent trees are missing
   their output (§4). jellyfin additionally has no `plugin.json`, so it cannot be
   loaded, inspected, or even identified without executing `bin/build.js`. The six
   no-build plugins can be pointed at by `mdev` as-is.
2. **The compiler hides the runtime.** This is the cost core `5706c66cf` paid.
   Its message: *"`02-html-parser` did not compile at all. Two ES6 template
   literals, and Duktape is ES5.1: `SyntaxError: invalid token` and the whole
   plugin fails to load. **tsc against `--target ES5` transpiles the construct
   instead of rejecting it, so the gate was green.**"* [CORE] A compiler asked to
   *emit* ES5 treats ES6 input as its job, not as an error. Every green
   type-check in this corpus that also emits carries that blind spot; the three
   `noEmit` configs do not, but they do not catch it either — they simply never
   claimed to.
3. **The toolchain rots faster than the plugin.** soap4.me pins gulp 3 and
   `babel-preset-es2015` (`package.json:29,28`), both long dead; the plugin is
   from 2016. dailymotion's compile is `compileOnSave`/`watch` in an editor
   (`tsconfig.json:2,14`) with no CLI entry point — reproducing that build in 2026
   means reconstructing somebody's 2016 IDE setup.
4. **A transpiler does not supply the library.** jellyfin still hand-writes
   `Object.entries` and `Object.values` (`src/polyfill.js:3-38`) because swc
   downlevels syntax only. Anyone who believes the build makes the runtime modern
   is wrong in a way that fails at runtime, not at build time.

**The recommendation this supports.** Write ES5 by hand, take types from
`.d.ts` + `noEmit`, and reserve a build for packaging (zip + generated manifest)
rather than compilation. Six of nine already do the first, three of nine already
do the second, and the two authors who built a *packaging* step — jellyfin and
soap4.me — converged on the same `package.json`-as-manifest-source design. The
only genuinely compiled plugin whose source needs it is jellyfin, and its own
`polyfill.js` shows the compiler solved half the problem.

---

## 7. Loose ends, honestly labelled

- **GLW views split three-way and cut across build style.** HDRezka ships 48
  `.view` files, tmdb 25, trakt 17; jellyfin, anilibria, youtube, qobuz,
  dailymotion and soap4.me ship none (jellyfin's `views/` holds only `.gitkeep`).
  **No plugin.json in the corpus declares a `glwviews` key**, which `plugins.c:751`
  reads — so views are reached from JS, not from the manifest. Not investigated
  further; feeds the map's open "GLW views in plugins" question. [READ] [CORE]
- **qobuz's own comment has drifted.** `qobuz.js:6` cites `src/plugins.c:687` for
  the apiversion default; in this core revision the ecmascript branch's line is
  `712`, and `688` is the *vmir* branch's identical statement. The claim is right,
  the citation points at the wrong branch. [READ] [CORE]
- **Not measured:** whether swc/tsc/Babel output for these repos actually loads in
  Movian. No build was run — three of the four toolchains have no installed
  `node_modules`, and running them would write into read-only plugin trees.
  HDRezka's memory A/B numbers are quoted from its comments, not reproduced.
