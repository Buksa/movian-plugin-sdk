---
name: view
description: Iterate on GLW `.view` files in a Movian plugin — live reload, isolated single-view preview against a fixture, turning a mockup into a view, widget-local debug tracing, focus/event tracing, and skin overrides. Use when asked to edit or debug a `.view` file, fix GLW layout or focus or rendering, preview a view outside the full app, or iterate on a skin.
---

# GLW view work in a plugin

> **Resolving `mdev` first.** Every `mdev` command below assumes the shim is
> reachable. It often is not: an agent session runs a **non-interactive** shell,
> which reads neither `~/.profile` nor `~/.bashrc`, so `mdev` is on `PATH` only
> if whatever launched the session happened to put it there. Do not rely on that.
>
> Once per session, before the first `mdev` command, resolve it from the path the
> installer recorded and use that path for the rest of the session:
>
> ```sh
> command -v mdev || jq -r '.bin + "/mdev"' ~/.config/movian-sdk/config.json
> ```
>
> If neither answers, the SDK is not installed here — say so rather than guessing
> a path: `cd movian-plugin-sdk && ./install.sh /abs/path/to/movian/checkout`.
> This preamble is repeated in every `movian:*` skill on purpose, because skills
> load individually and you may be holding only this one.


Plugins ship `.view` files, and they are parsed by the same GLW engine as the
built-in skin — so everything here applies whether the file lives in your plugin
or in the core's `glwskins/`.

All commands work from your plugin repo; `mdev` resolves the core itself. Where
a path into the core checkout is needed, `$(mdev core)` supplies it.

## The DSL reference set

- `references/glw-view-language.md` — the `.view` language: lexical elements, all
  five assignment operators (`=`, `?=`, `:=`, `<-`, `_=_`), the complete
  expression-function table (90 entries), prop scopes
  (`$self`/`$args`/`$parent`/`$view`/`$clone`/`$ui`/`$core`/`$nav`), event maps,
  and the preprocessor (`#define`/`#import`/`#include`).
  **Read this before writing a `.view` from scratch.**
- `references/glw-widget-catalog.md` — all 51 registered widget classes with
  flags, layout behaviour and class-specific attributes, plus the 116-entry
  global attribute table.
- `references/glw-patterns.md` — worked recipes: page skeleton with a preview
  fixture, list and grid pages, focus highlight, popups, settings rows, plugin
  data binding, debug moves.

`mdev viewdoc --check` diffs those reference docs against the core's C source
tables and exits nonzero on drift. It compares names only, in both directions:
an attribute or expression function present in the core but undocumented here
(`missing-from-doc`), and one documented here that this core does not implement
(`gone-from-source`). The core side comes from `generated/movian-metadata.json`,
so run the core's `support/devtools/metadata/gen.py --check` first before
reading `gone-from-source` as a doc bug — a stale artifact looks the same.

## The edit/reload loop

```
mdev run -p .            # once, if not already running
mdev reload [--shot]     # after each edit
mdev watch --shot        # or auto-reload on every save
```

`reload`/`watch` send the `ReloadUI` action (handled at `src/ui/glw/glw.c:2522`),
which is a **full view-cache flush** (`glw_load_universe()`,
`src/ui/glw/glw.c:404-423`): the whole widget tree is destroyed and
`universe.view` is rebuilt from scratch. Every `.view` under the active skin is re-parsed on every reload, not
just the file you edited — so an unrelated view with a pre-existing error will
surface on every reload. That also makes reload a full-fidelity replay of a fresh
launch's view loading.

### Known false green

`reload` and `preview` only grep for GLW **parser/preprocessor** errors, plus (for
preview) the preview plugin's own error line. A `.view` **lexer** error — an
unterminated string literal — or a failure to open the target file matches
neither pattern: the command exits 0 and reports a clean reload while the view
did not load.

So: never treat a green reload as full proof for a change that could fail at
lexer level or on a path typo. Follow with `mdev log --tail 40` or a screenshot,
and look for any `GLW` line near the reload.

## Reloading plugin JS is a different command

`mdev reload` and `mdev watch` are **views-only** — they never reload a dev
plugin's JS. For `.js` changes use `--js`, which sends `ReloadData`: it
force-reloads every `-p` plugin's ECMAScript **and** reopens the current page as
a side effect, so page state does not survive. See `movian:run` before trusting
its exit code.

## Isolated single-view preview

```
mdev preview <file.view> [--fixture <fixture.json>] [--shot]

# e.g. from the plugin repo root:
mdev preview views/episodes.view --fixture fixtures/episodes.json --shot
```

Renders one view with no navbar, sidebar or directory chrome around it, through
a `page.type = "raw"` page whose `metadata.glwview` points straight at your file.

**The fixture is JSON, not a view.** It supplies the page model your view binds
against, so you can iterate on markup without a live data source. Fixtures belong
in your plugin repo next to the views they feed — nothing scaffolds them for you,
so the first one is written by hand.

Schema v1, all three top-level keys optional (an empty `{}` is valid):

```json
{
  "metadata": { "title": "Episodes", "subtitle": "Season 2" },
  "args":     { "id": "42" },
  "nodes": [
    { "type": "item", "url": "x:1",
      "metadata": { "title": "Episode 1", "icon": "../fixtures/img/ep1.png" } }
  ]
}
```

- `metadata` lands on `$self.model.metadata.*`, `args` on `$self.args.*`.
- Each `nodes[]` entry becomes one `page.appendItem(url, type, metadata)`, i.e.
  one child of `$self.model.nodes`. Extra keys on a node are copied onto that
  node's own prop root verbatim — that is how a cloner reaches `$self.episode`.
- Any other top-level key is copied onto `$self.model.*` verbatim.
- Unknown keys are **never rejected**; they simply become props.

Full schema and worked examples: `$(mdev core)/support/devtools/viewpreview/`
— `README.md`, plus `fixtures/minimal.json` (metadata only),
`fixtures/directory-nodes.json` (12 items) and `views/demo-list.view`, the target
view that consumes both.

**A broken preview is never a silent black screen.** A missing view, a missing
fixture, malformed fixture JSON, or any exception applying it is caught: the page
switches to the preview plugin's own `error.view`, the message appears on screen
in `page.metadata.viewpreviewError` **and** in the log as
`viewpreview: ERROR: <message>`. A GLW parse error in the target view cannot be
caught in JS, but is logged as `GLW [ERROR]: Error <file>:<line>: <message>`.
`mdev preview` greps for both patterns and **exits 1** if either appears.

Worth restating:

- **Relative paths work, but only because the shim fixes them.** The core's
  `mdev preview` and `mdev watch --dir` absolutise a relative path against the
  *core checkout* rather than your cwd (`resolve_repo_path`,
  `mdevlib/cli.py:452-458`) — the one place in the harness that does, since `-p`
  and `--skin` both use the caller's cwd. From a plugin repo that would aim
  `mdev preview views/x.view` at `<core>/views/x.view`. The `mdev` shim rewrites
  such an argument to an absolute path when it exists relative to your cwd, and
  leaves it alone otherwise, so the core's own fallback still applies. If you
  invoke the core's `mdev` directly instead of the shim, pass absolute paths.
- The preview instance always launches with `--bypass-ecmascript-acl`. Without it
  the ECMAScript file ACL (`filename_is_allowed()`, `src/ecmascript/es_fs.c:91`)
  confines the preview plugin's reads to its own directory, and it must read your
  fixture and view from anywhere. Required, not a convenience.
- Target views must bind through `$self.model.*` / `$self.args.*`, **not**
  `$page.*`. Some third-party plugin views use `$page.*` by convention, but it
  has no scope root in this core (`src/ui/glw/glw_scope.c:54-61`,
  `src/ui/glw/glw.h:290-297`) and will silently bind nothing.
- Views can be referenced by a plain absolute filesystem path — no scheme prefix
  or symlink needed (`fa_resolve_proto`, `src/fileaccess/fileaccess.c:99-113`: no
  `scheme://` means "assume a plain file").
- Reusing an already-running instance that was not started with the preview
  plugin will fail to resolve the preview route. Use a dedicated `--name`, or
  `mdev stop --name preview` first.

## Mockup → view

Turning a reference image into a working `.view`. This sequence converged in 7
rounds on the pilot page; follow it in order.

1. **Fixture first.** Extract every piece of visible text and data into a
   schema-v1 fixture (`metadata` for page-level fields, extra top-level keys land
   on `$self.model.*`, `nodes[]` for list rows, per-node extra keys on the node
   root). Generate placeholder art — never commit third-party images. Relative
   `source:` paths resolve against the *view file's* directory
   (`glw_resolve_path` -> `fa_absolute_path`, `src/ui/glw/glw_view_attrib.c:36-59`),
   so `"../fixtures/" + $self.metadata.icon` works from `views/`.
2. **Write convergence criteria before the first render.** Must match: element
   presence and nesting, column proportions, alignment, focus state. Accepted
   deltas: fonts and antialiasing, exact colours, placeholder art, icon glyphs.
   Without this list you will chase pixels forever.
3. **Static gate before every render:**
   `"$(mdev core)"/build.debug/movian-analyze --check <view>` — instant, catches
   parse errors without touching the instance. Macro note: GLW `#define` bodies
   must be `{ ... }` blocks; expression-shaped macros do not parse.
4. **Render and screenshot:** `mdev preview <view> --fixture <json> --shot`, then
   iterate with `mdev reload --name preview` + `mdev shot --name preview`. If the
   page never opens or the screenshot endpoint times out, the instance is wedged
   — `mdev stop --name preview` and relaunch (see
   `movian:verify` → `references/CONSTRAINTS.md`).
5. **Compare multimodally**, fix the worst structural delta first, repeat.
   Layout gotchas that each cost a round:
   - In a `container_x`, a child column with its own content constraint ignores
     `weight:` — set `filterConstraintX: true;` on the column so weights govern.
   - To right-align a trailing label, interpose `widget(dummy, { });` and make
     the row's parent column `filterConstraintX: true;`.
   - Progress bars: a `container_z` of a dim full-width quad plus a `container_x`
     of `quad(weight: $self.progress)` / `dummy(weight: 1 - $self.progress)`.
   - `backdrop` border-scaling draws only the vertical border bands — top and
     bottom never render, with skin or custom 9-slice PNGs alike. Build outline
     frames from four quads instead.
6. **Focus states:** the *first* arrow sent to a fresh instance is consumed by the
   mouse→keyboard mode switch, and initial focus lands by weight at page load.
   Drive focus with a few `/api/input/action/up|down` calls before the comparison
   shot, and verify it visually.

## Widget-local debug tracing

Add `debug: true` to one widget for layout-box, texture-size, text-layout and
prop-subscription tracing scoped to **that widget only** — far lower noise than
global tracing for a single-widget investigation:

```view
widget(container_x, {
  debug: true;
  ...
});
```

Anchor: `src/ui/glw/glw_view_attrib.c:1382` — `{"debug", mod_flag, GLW2_DEBUG,
mod_flags2}`. `GLW2_DEBUG` also enables `PROP_SUB_DEBUG` in `glw_view_eval.c`,
and the widget-local prints live in `glw_image.c`, `glw_text_bitmap.c` and
`glw_container.c`.

Remove it before shipping unless the task explicitly wants it kept.

## `--debug-glw` and its two limits

Global event/focus routing logs for the whole UI. Not an `mdev run` flag — see
`movian:verify` → `references/debug-flags.md` for the launch form and
runtime-verified log examples. Two documented limits:

- it does **not** draw layout boxes on every widget — use `debug: true` for that;
- it does **not** make the visual list cursor appear. The row highlight needs real
  GLW keyboard mode, which `/api/input/action/<Action>` does not enable because
  those events are not keypresses. A screenshot that must show the cursor needs a
  real X11 keypress, via the core's `mdevlib/x11_keypress.py`.

## Skin overrides

`mdev run --skin <dir>` (core flag, parsed at `src/main.c:733-735`) points GLW at
an alternate skin directory instead of the default. Iterate on a copy rather than the tracked tree:

```
cp -r "$(mdev core)/glwskins/flat" /tmp/skin-experiment
mdev run --name skin-test --skin /tmp/skin-experiment
mdev watch --name skin-test --dir /tmp/skin-experiment --shot
```

Pass `--dir` an absolute path — see the preview caveat above.

## Views from another fork may use builtins this core lacks

A plugin view written against a different Movian fork can call JS builtins this
core does not implement. Observed: `movian-plugin-tmdb/views/posters.view` calls
`isReady()`, which is unimplemented here and renders as the literal text
`Unknown function` in the UI. It is **not** a load failure — the view loads and
reload/preview report clean, while another view in the same plugin works fine.

Treat any view sourced from outside as a candidate for this. A green reload plus
a visibly broken screenshot together mean "unsupported builtin", not "GLW error".
