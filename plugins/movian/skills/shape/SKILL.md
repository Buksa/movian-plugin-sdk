---
name: shape
description: The structure of a Movian plugin repo — plugin.json manifest fields, entry point, where views and libraries go, and what changes as a plugin grows. Use when starting a new Movian plugin, when orienting in an unfamiliar plugin repo, when editing plugin.json, or when deciding where a new file belongs.
---

# The shape of a Movian plugin

> **Resolving `mdev` first.** Every `mdev` command below assumes the shim is
> reachable. It often is not: an agent session runs a **non-login,
> non-interactive** shell, which reads neither `~/.profile` nor `~/.bashrc`, so
> `mdev` is on `PATH` only if whatever launched the session happened to put it
> there. (A login shell — `bash -lc` — *is* non-interactive but does read
> `~/.profile`; the shape without any startup file is the plain `bash -c` an
> agent gets.) Do not rely on inheritance.
>
> Once per session, before the first `mdev` command, resolve it and use the
> resolved path for the rest of the session:
>
> ```sh
> command -v mdev \
>   || { p="$(jq -er '.bin // empty' "${MOVIAN_SDK_CONFIG:-$HOME/.config/movian-sdk/config.json}")/mdev" \
>        && [ -x "$p" ] && printf '%s\n' "$p"; } \
>   || { p="${MOVIAN_SDK_BINDIR:-$HOME/.local/bin}/mdev"; [ -x "$p" ] && printf '%s\n' "$p"; }
> ```
>
> Three steps, each earning its place. `jq -er` with `// empty` because a config
> written before the `bin` key existed would otherwise make `.bin + "/mdev"`
> print **`/mdev`** — a nonexistent path, with exit 0. `[ -x ]` because a
> recorded path that no longer exists must not be handed back as an answer. And
> the last step because `./install.sh` **without** a core path installs the shims
> and writes no config at all, so a config-only lookup would report "not
> installed" on a machine where `mdev` is sitting in `~/.local/bin`.
>
> If none of the three answers, the SDK really is absent here — say so rather
> than guessing a path, and point at the installer:
> `cd movian-plugin-sdk && ./install.sh /abs/path/to/movian/checkout`.
> This preamble is repeated in every `movian:*` skill on purpose, because skills
> load individually and you may be holding only this one. `tests/reachable_selftest.py`
> asserts that all seven copies stay identical.


Generalised from the five plugins on this machine — `tmdb`, `trakt`, `anilibria`,
`qobuz`, `HDRezka` — which between them span the whole range from one file to a
full application.

## The irreducible minimum

A plugin is a directory with a manifest and an entry script. Nothing else is
required:

```
plugin.json          # the manifest
<entry>.js           # named by plugin.json's "file"
logo.png             # named by "icon"
```

`tmdb` is essentially this, and it works.

## `plugin.json`

Eleven fields appear in **all five** plugins, so treat them as the baseline:

```json
{
  "type": "ecmascript",
  "apiversion": 1,
  "id": "tmdb",
  "file": "tmdb.js",
  "showtimeVersion": "5.0",
  "version": "1.3.7",
  "author": "facanferff",
  "title": "TMDb",
  "icon": "logo.png",
  "category": "other",
  "synopsis": "...",
  "description": "..."
}
```

- `id` must be unique — it is the plugin's identity to the app, not a display name.
- `file` is the entry point, relative to the plugin root.
- `type` is `ecmascript` for every JS plugin.
- `category` drives placement in the UI.
- Key **order is not significant**; the five repos disagree on it freely.

`homepage` appears in some (`HDRezka`, `qobuz`) and is optional. `downloadURL`
appears only in `HDRezka`, which self-updates — that belongs to distribution, not
development.

## Where things go as it grows

The repos agree on more than they disagree:

| directory | holds | seen in |
|---|---|---|
| `views/` | GLW `.view` files | tmdb, trakt, HDRezka |
| `lib/` or `libs/` or `utils/` | shared JS helpers | anilibria, trakt, HDRezka |
| `src/` | source when the entry is a thin shim | trakt |

`HDRezka` shows what a large plugin becomes: `pages/`, `routes/`, `parsers/`,
`model/`, `api/`, `ui/`, `service.js` split out of the entry file, plus
`tests/`, `types/`, `tsconfig.json` and a build pipeline. That is a destination,
not a starting point — do not scaffold it up front.

## The entry file

The entry registers what the plugin offers, then returns. It does not loop or
block. Typical first moves: create a service so the plugin appears in the UI,
register routes for the URLs it handles, declare settings.

For exact call sequences read the runnable examples rather than prose:
`$(mdev core)/plugin_examples/` has eight, one per concern —
`async_page_load`, `itemhook`, `listx_cloner`, `music`, `settings`,
`subscriptions`, `videoscrobbling`, `webpopupplugin`. The `movian:api` skill
covers which modules exist and where their semantics are documented.

## Two constraints that shape the code

- **Duktape, ES5.1.** No `let`/`const`, no arrow functions, no template literals,
  no `Promise`. This is the single most common cause of a plugin that reviews
  cleanly and fails at parse time.
- **Filesystem ACL.** A plugin's `fs` reads are confined to its own directory.
  Reading outside it fails at runtime, not at load.

## Running it

From the plugin repo, with no files added to it:

```
mdev run -p .
```

`-p` resolves relative to your cwd, so `.` is this plugin. See `movian:run` for
the loop and `movian:verify` for what counts as proof it works.

## What varies and should not be copied blindly

Of the five, only `HDRezka` and `trakt` have a git remote; `anilibria`, `qobuz`
and `tmdb` have none. Only `HDRezka` has an `AGENTS.md`, a `CONTEXT.md`, tests
and a build step. None of that is required to be a working plugin — it is what a
plugin accretes when it becomes a project.
