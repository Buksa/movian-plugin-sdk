---
name: shape
description: The structure of a Movian plugin repo — plugin.json manifest fields, entry point, where views and libraries go, and what changes as a plugin grows. Use when starting a new Movian plugin, when orienting in an unfamiliar plugin repo, when editing plugin.json, or when deciding where a new file belongs.
---

# The shape of a Movian plugin

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
