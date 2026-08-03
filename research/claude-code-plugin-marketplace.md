# How a Claude Code plugin marketplace actually works

Research for [issue #2](https://github.com/Buksa/movian-plugin-sdk/issues/2).
Investigated 2026-08-02 against Claude Code **v2.1.220**.

**Sources.** Three kinds, marked throughout:

- **[EXAMPLE]** — the working marketplaces installed on this machine:
  `~/.claude/plugins/marketplaces/openai-codex` (a clone of `openai/codex-plugin-cc`)
  and `~/.claude/plugins/marketplaces/claude-plugins-official` (Anthropic's official
  catalog, which ships a canonical `example-plugin`).
- **[DOCS]** — official Claude Code documentation, URL cited per claim.
- **[TESTED]** — experiments run locally against a throwaway marketplace
  (`/tmp/mp-test/sdk-probe`), added, installed, updated and removed on this machine.
  All test artifacts were removed afterwards; `known_marketplaces.json` and
  `installed_plugins.json` were verified back to their original contents.

---

## 0. The headline answer for this repo

**The mechanism does what the SDK needs.** A marketplace-installed plugin delivers its
skills to sessions running in *any* other repo, with **zero files added to that repo**,
and **cannot collide** with that repo's own `.claude/skills/`.

Two facts carry it:

1. A plugin installed at **user scope** is recorded in `~/.claude/` only, and applies
   across all projects. [DOCS][scopes] Verified: with the probe plugin installed at user
   scope, `claude plugin list` run from `~/movian-plugin-HDRezka` listed it, and that
   repo's `.claude/` contains only `worktrees/` — no skills, no settings, nothing
   added. [TESTED]
2. Plugin skills are namespaced `plugin-name:skill-name`, and the docs state plainly:
   *"Plugin skills use a `plugin-name:skill-name` namespace, so they cannot conflict
   with other levels."* [DOCS][skills-where]

The one genuine constraint is the **development loop**, not delivery — see §4. Marketplace
plugins are *copied* into a versioned cache, so editing the SDK working tree does not
change what a session sees. That is solvable (`--plugin-dir`, or a skills-dir plugin),
but it must be a deliberate choice. Details in §4 and §7.

---

## 1. Manifest

### 1.1 The marketplace manifest

**Exact path: `.claude-plugin/marketplace.json`, at the repository root.** The directory
name is literal and hyphenated; the repo root is the directory *containing*
`.claude-plugin/`. [DOCS][mkt-create] A GitHub repo becomes a marketplace by containing
this one file — there is no registration step, no publish, no account. Adding the repo
is what makes it a marketplace to a given user.

Real, complete example — `~/.claude/plugins/marketplaces/openai-codex/.claude-plugin/marketplace.json`
[EXAMPLE], verbatim:

```json
{
  "name": "openai-codex",
  "owner": {
    "name": "OpenAI"
  },
  "metadata": {
    "description": "Codex plugins to use in Claude Code for delegation and code review.",
    "version": "1.0.6"
  },
  "plugins": [
    {
      "name": "codex",
      "description": "Use Codex from Claude Code to review code or delegate tasks.",
      "version": "1.0.6",
      "author": {
        "name": "OpenAI"
      },
      "source": "./plugins/codex"
    }
  ]
}
```

**Required top-level fields:** `name`, `owner`, `plugins`. [DOCS][mkt-create]

**Optional top-level fields** [DOCS][mkt-create]:

| Field | Type | Notes |
| :-- | :-- | :-- |
| `$schema` | string | For editor autocomplete. **Claude Code ignores it at load time.** |
| `description` | string | Marketplace description |
| `version` | string | Marketplace manifest version |
| `metadata.pluginRoot` | string | Base dir prepended to relative plugin sources — `"./plugins"` lets entries say `"source": "formatter"` |
| `allowCrossMarketplaceDependenciesOn` | array | Marketplaces this one's plugins may depend on |
| `renames` | object | Former plugin name → current name (or `null` if removed), so existing users migrate. Needs v2.1.193+ |

`description` and `version` are also accepted nested under `metadata` for backward
compatibility — which is the form the OpenAI marketplace uses. [DOCS][mkt-create] [EXAMPLE]

> **Gap / caveat.** The official marketplace declares
> `"$schema": "https://anthropic.com/claude-code/marketplace.schema.json"`
> (`~/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json`),
> but that URL **returns HTTP 404**. [TESTED] It is a nominal identifier, not a live
> document. Do not plan on fetching it. `claude plugin validate` is the working
> substitute (§6).

**Plugin entries.** Each entry requires only `name` and `source`. [DOCS][mkt-entries]
Optional: `displayName`, `description`, `version`, `author`, `homepage`, `repository`,
`license`, `keywords`, `category`, `tags`, `strict`, `relevance`, `defaultEnabled`, plus
component-path fields `skills`, `commands`, `agents`, `hooks`, `mcpServers`, `lspServers`.

**Plugin `source` forms** [DOCS][mkt-sources]:

| Source | Type | Fields | Notes |
| :-- | :-- | :-- | :-- |
| Relative path | string, e.g. `"./my-plugin"` | — | Must start with `./`; resolved against the **marketplace root**, not `.claude-plugin/` |
| `github` | object | `repo`, `ref?`, `sha?` | |
| `url` | object | `url`, `ref?`, `sha?` | Any git URL |
| `git-subdir` | object | `url`, `path`, `ref?`, `sha?` | Sparse clone of a monorepo subdir |
| `npm` | object | `package`, `version?`, `registry?` | Installed via `npm install` |

For the SDK, the relative-path form (`"./plugins/movian"`) is right: the plugin lives in
the same repo as the marketplace.

### 1.2 The plugin manifest

**Exact path: `<plugin-root>/.claude-plugin/plugin.json`.** [DOCS][plugin-schema]

**The manifest is optional.** *"If omitted, Claude Code auto-discovers components in
default locations and derives the plugin name from the directory name."*
[DOCS][plugin-schema] Include one anyway, for the name and metadata.

Real example — `.../openai-codex/plugins/codex/.claude-plugin/plugin.json` [EXAMPLE]:

```json
{
  "name": "codex",
  "version": "1.0.6",
  "description": "Use Codex from Claude Code to review code or delegate tasks.",
  "author": { "name": "OpenAI" }
}
```

**`name` is the only required field.** [DOCS][plugin-schema] Anthropic's own
`example-plugin` omits `version` entirely
(`.../claude-plugins-official/plugins/example-plugin/.claude-plugin/plugin.json`)
[EXAMPLE] — that is the recommended shape for an actively developed plugin (§4.3).

`name` is what namespaces every component: the agent `agent-creator` in plugin
`plugin-dev` surfaces as `plugin-dev:agent-creator`. [DOCS][plugin-schema]

Useful optional fields: `displayName` (UI only, not used for namespacing, v2.1.143+),
`version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`,
`defaultEnabled` (v2.1.154+). Component-path overrides: `skills`, `commands`, `agents`,
`workflows`, `hooks`, `mcpServers`, `outputStyles`, `lspServers`, `userConfig`,
`dependencies`. [DOCS][plugin-schema]

**Unrecognized top-level fields are ignored**, so one manifest can double as an npm or
VS Code manifest; `claude plugin validate` reports them as warnings, not errors. Fields
with the *wrong type* still fail hard. [DOCS][plugin-schema]

---

## 2. Layout: how skills are discovered

**Skills are auto-discovered. Nothing declares them.** The docs: *"Skills and commands
are automatically discovered when the plugin is installed."* [DOCS][ref-skills]
Confirmed against the example: `plugins/codex/.claude-plugin/plugin.json` has **no**
`skills` field, yet all three of its skills load. [EXAMPLE]

The rule is the directory scan:

```
<plugin-root>/
├── .claude-plugin/
│   └── plugin.json          # optional manifest
├── skills/                  # ← auto-scanned
│   ├── my-skill/
│   │   ├── SKILL.md         # required entrypoint
│   │   ├── references/      # optional supporting files
│   │   └── scripts/
│   └── other-skill/
│       └── SKILL.md
├── commands/                # legacy flat .md skills, also auto-scanned
├── agents/                  # subagent .md definitions
├── hooks/hooks.json
├── .mcp.json
└── .lsp.json
```

[DOCS][ref-layout] — matches the installed example exactly, which has
`skills/{codex-cli-runtime,codex-result-handling,gpt-5-4-prompting}/SKILL.md`,
`commands/*.md`, `agents/codex-rescue.md`, and `hooks/hooks.json`. [EXAMPLE]

Each skill is **a directory containing `SKILL.md`** — `skills/<name>/SKILL.md`. A bare
`.md` file under `skills/` is not a skill.

**SKILL.md frontmatter.** `name` and `description` required; `version` and `license`
optional. For user-invoked (slash-command) skills, also `argument-hint`,
`allowed-tools`, `model`. [EXAMPLE — `.../example-plugin/skills/example-skill/SKILL.md`
and `.../skills/example-command/SKILL.md`]

The `description` is the trigger. Anthropic's own guidance in the example skill:
*"description (required): Trigger conditions — describe when Claude should use this
skill"*, with the recommended pattern
`This skill should be used when the user asks to "phrase", "another phrase", mentions
"keyword", or discusses topic-area.` [EXAMPLE]

**Commands are legacy.** Anthropic's `example-plugin/README.md` states it outright:
*"The `commands/*.md` layout is a legacy format. It is loaded identically to
`skills/<name>/SKILL.md` — the only difference is file layout. For new plugins, prefer
the `skills/` directory format."* [EXAMPLE] The SDK should use `skills/` only.

**Agents** are declared by dropping a `.md` file in `agents/`, auto-scanned the same
way. [DOCS][ref-layout] [EXAMPLE — `agents/codex-rescue.md` surfaces as the agent type
`codex:codex-rescue`]

**Three special cases worth knowing** [DOCS][ref-paths]:

- A plugin with a `SKILL.md` at its root, no `skills/` dir and no `skills` manifest
  field, loads as a **single-skill plugin** (v2.1.142+).
- The `skills` manifest field *adds to* the default scan rather than replacing it —
  unlike `commands`/`agents`, which replace.
- With `"source": "./"` (plugin rooted at the marketplace root), listed `skills` paths
  become the complete set for that entry — the way several plugin entries can share one
  `skills/` folder.

**`${CLAUDE_PLUGIN_ROOT}`** resolves to the plugin's install directory; use it in hook
commands and MCP configs, because plugins are copied to a cache path that is not the
repo path. [DOCS][ref-caching] For state that must survive updates use
`${CLAUDE_PLUGIN_DATA}`. Relevant to the SDK: scripts must be referenced through
`${CLAUDE_PLUGIN_ROOT}`, and **paths that traverse outside the plugin root (`../shared`)
do not work after installation** — those files are not copied into the cache.
[DOCS][ref-caching]

---

## 3. Install and update

### 3.1 Commands

Two surfaces, same engine: `/plugin ...` inside a session, `claude plugin ...` from the
shell (scriptable, no interactive panel). [DOCS][discover-manage]

```bash
# 1. Register the catalog. Nothing is installed yet.
claude plugin marketplace add Buksa/movian-plugin-sdk

# 2. Install a plugin from it.
claude plugin install movian@movian-plugin-sdk            # --scope user (default)
claude plugin install movian@movian-plugin-sdk --scope project

# 3. Activate in the current session (otherwise it loads next launch).
/reload-plugins

# management
claude plugin list                       # --enabled / --disabled
claude plugin details movian             # component inventory + token cost
claude plugin update movian@movian-plugin-sdk
claude plugin disable|enable|uninstall movian@movian-plugin-sdk
claude plugin marketplace update movian-plugin-sdk
claude plugin marketplace remove movian-plugin-sdk        # also uninstalls its plugins
```

Adding a marketplace and installing a plugin are **two separate steps**.
[DOCS][discover-how]

> **[TESTED] gotcha.** `claude plugin update <name>` with the bare plugin name fails
> with `Plugin "probe" not found`. The **full `plugin@marketplace` id is required**:
> `claude plugin update probe@probe-mp` → `Plugin "probe" updated from 0.1.0 to 0.1.1`.
> `install`, `disable`, `enable` and `uninstall` all take the qualified id too.

> **[TESTED] gotcha.** `/reload-plugins` reports a skills count covering only the
> plugin's `commands/` directory, so it can print `0 skills` even when `skills/` loaded
> fine. [DOCS][discover-reload] Don't read that as failure.

### 3.2 Versioning, and what `gitCommitSha` implies

Version resolution, first one set wins [DOCS][mkt-version]:

1. `version` in the plugin's `plugin.json`
2. `version` in the marketplace entry
3. **the git commit SHA of the plugin's source**

The installed version determines the cache path and update detection: *"if the resolved
version matches what a user already has, `/plugin update` and auto-update skip the
plugin."* [DOCS][mkt-version]

`~/.claude/plugins/installed_plugins.json` on this machine [EXAMPLE]:

```json
"codex@openai-codex": [
  {
    "scope": "user",
    "installPath": "/home/uzver/.claude/plugins/cache/openai-codex/codex/1.0.6",
    "version": "1.0.6",
    "installedAt": "2026-07-17T02:40:17.506Z",
    "lastUpdated": "2026-07-17T02:40:17.506Z",
    "gitCommitSha": "db52e28f4d9ded852ab3942cea316258ae4ef346"
  }
]
```

**What the pinned `gitCommitSha` implies.** The codex plugin sets `"version": "1.0.6"`
in both manifests, so the *version string* is the update key and the SHA is a record of
what was fetched, not the pin that drives updates. The consequence, which the docs flag
as a warning: *"Setting `version` pins the plugin. If `plugin.json` declares
`"version": "1.0.0"`, pushing new commits without changing that string does nothing for
existing users, because Claude Code sees the same version and keeps the cached copy.
Bump the field on every release, or omit it to use the commit SHA."* [DOCS][mkt-version]

Confirmed directly [TESTED]: with `version` fixed at `0.1.0`, committing an edited
`SKILL.md` and running `claude plugin marketplace update` + `claude plugin update` left
the cache at `.../probe/0.1.0/` with the **old** content. Bumping both manifests to
`0.1.1` and re-running produced a new cache directory `.../probe/0.1.1/` carrying the
edit, and `installed_plugins.json` moved to `version: 0.1.1` with a new `gitCommitSha`.

**Recommendation for the SDK: omit `version` from both manifests.** Then every commit is
a new version and `claude plugin update` just works. *"For the git-based source types
`github`, `url`, `git-subdir`, and relative paths inside a git-hosted marketplace, you
can omit `version` entirely and every new commit is treated as a new version. This is
the simplest setup for internal or actively-developed plugins."* [DOCS][mkt-version]

Also: *"Avoid setting `version` in both `plugin.json` and the marketplace entry. Claude
Code always uses the `plugin.json` value without warning, so a stale manifest version
can mask a version you set in `marketplace.json`."* [DOCS][mkt-version]

**Auto-update:** off by default for third-party and local marketplaces, on for official
Anthropic ones. Toggled per-marketplace in `/plugin` → Marketplaces.
[DOCS][discover-autoupdate] So SDK consumers will need an explicit
`claude plugin update`, or must switch auto-update on.

---

## 4. Local and branch installation — the verdict

### 4.1 Local filesystem path — **YES, unambiguously**

```bash
claude plugin marketplace add ./my-marketplace          # a directory
claude plugin marketplace add ./path/to/marketplace.json # or the file directly
```

[DOCS][discover-add] The CLI's own help says the argument is *"a URL, path, or GitHub
repo"*.

Verified end to end. [TESTED] `claude plugin marketplace add /tmp/mp-test/sdk-probe`
→ `✔ Successfully added marketplace: probe-mp (declared in user settings)`, listed as
`Source: Directory (/tmp/mp-test/sdk-probe)`, and recorded in
`~/.claude/plugins/known_marketplaces.json` as:

```json
"probe-mp": {
  "source": { "source": "directory", "path": "/tmp/mp-test/sdk-probe" },
  "installLocation": "/tmp/mp-test/sdk-probe",
  "lastUpdated": "2026-08-02T18:54:54.470Z"
}
```

Note `installLocation` **is the working tree itself** — a directory marketplace is not
cloned. The *catalog* is read in place. Installing `probe@probe-mp` then succeeded and
`claude plugin details probe` reported `Skills (1) probe-skill`. [TESTED]

The repo does not even need to be pushed, or be a git repo at all, for the marketplace
to be added.

### 4.2 Non-default branch — **YES for git URLs, via a `#ref` suffix**

*"To add a specific branch or tag, append `#` followed by the ref."* [DOCS][discover-add]

```bash
claude plugin marketplace add https://github.com/Buksa/movian-plugin-sdk.git#research/marketplace
claude plugin marketplace add https://gitlab.com/company/plugins.git#v1.0.0
```

Verified the ref genuinely reaches git. [TESTED]
`claude plugin marketplace add "https://github.com/openai/codex-plugin-cc.git#nonexistent-xyz"`
→

```
✘ Failed to add marketplace: Failed to clone marketplace repository:
warning: Could not find remote branch nonexistent-xyz to clone.
fatal: Remote branch nonexistent-xyz not found in upstream origin
```

That is `git clone --branch` refusing the ref — the suffix is parsed and passed through,
not ignored.

The `owner/repo` shorthand accepts `#ref` too. [TESTED] `openai/codex-plugin-cc#nonexistent-xyz`
first failed on SSH auth (shorthand clones over SSH by default, and this machine has no
SSH key); re-run as `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1 claude plugin marketplace add
"openai/codex-plugin-cc#nonexistent-xyz"` it reached the same
`Remote branch nonexistent-xyz not found` error. So the ref is honoured on both forms —
but on this machine the `owner/repo` form needs `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`
(there is no SSH key), or the full `https://...` URL. [DOCS][mkt-private] documents the
SSH-by-default behaviour and that env var.

**Two limits found by testing, both worth knowing:**

- `file://` URLs are **rejected**: `file:///tmp/mp-test/sdk-probe#feature-branch` →
  `✘ Invalid marketplace source format. Try: owner/repo, https://..., or ./path`.
  [TESTED] So you cannot combine a local path with a branch ref. Local means *the
  working tree as it currently stands*, whichever branch is checked out.
- A **marketplace** source supports `ref` but **not** `sha`; only a **plugin** source
  inside `marketplace.json` supports both. [DOCS][mkt-sources]

### 4.3 The real constraint on the dev loop

Local and branch installs both work, but neither makes the SDK live-editable, because of
caching:

> *"For security and verification purposes, Claude Code copies marketplace plugins to
> the user's local plugin cache (`~/.claude/plugins/cache`) rather than using them
> in-place."* [DOCS][ref-caching]

Demonstrated. [TESTED] With `probe` installed from the *directory* marketplace, editing
`/tmp/mp-test/sdk-probe/plugins/probe/skills/probe-skill/SKILL.md` left
`~/.claude/plugins/cache/probe-mp/probe/0.1.0/skills/probe-skill/SKILL.md` unchanged.
The marketplace *catalog* is read in place; the *plugin* is always copied.

So: local-path install removes the need to **push**, but not the need to **reinstall or
update**. For a genuinely live loop, use one of these instead:

- **`claude --plugin-dir <path>`** — loads a plugin for the duration of the session, no
  install, no cache copy. [DOCS][ref-caching] Best fit for iterating on the SDK. Note
  such plugins show in `claude plugin list` only when the flag precedes the subcommand
  (`claude --plugin-dir <dir> plugin list`). [DOCS][ref-listing]
- **A skills-directory plugin** — any folder under `~/.claude/skills/` containing
  `.claude-plugin/plugin.json` loads as `<name>@skills-dir` on the next session, with no
  marketplace and no install step, *"discovered in place rather than copied into the
  plugin cache"*. [DOCS][ref-skillsdir] `SKILL.md` edits then take effect immediately in
  the running session; changes to `hooks/`, `.mcp.json`, `agents/`, `output-styles/`
  still need `/reload-plugins`. [DOCS][ref-skillsdir] Scaffold with `claude plugin init`.

A practical arrangement: develop against `--plugin-dir ~/movian-plugin-sdk/plugins/movian`,
and ship the same tree through the marketplace. The layout is identical either way,
which is the main reason to get the layout right up front.

---

## 5. Scope, and interaction with a repo's own `.claude/skills/`

### 5.1 Installation scopes

| Scope | Settings file | Meaning |
| :-- | :-- | :-- |
| `user` | `~/.claude/settings.json` | Personal, across **all** projects (default) |
| `project` | `.claude/settings.json` | Team, shared via version control |
| `local` | `.claude/settings.local.json` | This repo, you only; gitignored |
| `managed` | managed settings | Admin-installed, read-only |

[DOCS][scopes] Selected with `--scope` on `claude plugin install`. [DOCS][discover-install]

**For the SDK's stated goal — zero files in the plugin repos — user scope is the only
correct choice.** Project scope writes `.claude/settings.json` *into the plugin repo*,
which is exactly what must not happen. Verified: a user-scope install touches only
`~/.claude/plugins/installed_plugins.json` and `~/.claude/settings.json`; nothing is
written to the project. [TESTED]

The alternative, `extraKnownMarketplaces` in a project's `.claude/settings.json`
[DOCS][mkt-team], is the "team" pattern — it prompts collaborators to install the
marketplace on folder trust. It is genuinely useful, but it **adds a file to the plugin
repo**, so it does not meet the zero-files constraint. Worth offering as an opt-in for
other contributors, not as the default.

### 5.2 Name collisions — plugin skills cannot collide

Where skills come from [DOCS][skills-where]:

| Location | Path | Applies to |
| :-- | :-- | :-- |
| Enterprise | managed settings | Whole org |
| Personal | `~/.claude/skills/<name>/SKILL.md` | All your projects |
| Project | `.claude/skills/<name>/SKILL.md` | That project |
| Plugin | `<plugin>/skills/<name>/SKILL.md` | Wherever the plugin is enabled |

The precedence rule, verbatim [DOCS][skills-where]:

> *"When skills share the same name across levels, enterprise overrides personal, and
> personal overrides project. A skill at any of these levels also overrides a bundled
> skill with the same name. [...] **Plugin skills use a `plugin-name:skill-name`
> namespace, so they cannot conflict with other levels.** If you have files in
> `.claude/commands/`, those work the same way, but if a skill and a command share the
> same name, the skill takes precedence."*

**So, precisely:**

- Enterprise > personal > project. Any of these overrides a bundled skill of the same
  name (a project `code-review` replaces the built-in `/code-review`).
- **Plugin skills sit outside that ladder entirely.** Nothing shadows them and they
  shadow nothing. A `movian:build` skill and a repo's own `.claude/skills/build/` are
  two distinct skills, both available, invoked as `/movian:build` and `/build`.
- Corroborated on this machine: the codex plugin's components surface as
  `codex:codex-cli-runtime`, `codex:gpt-5-4-prompting`, `codex:rescue`, and the agent
  type `codex:codex-rescue` — all prefixed, none bare. [EXAMPLE]

**Implication for the SDK:** it is safe. The SDK cannot break an existing plugin repo's
skills, and a plugin repo cannot accidentally override an SDK skill. The cost is that
invocation is always qualified — users type `/movian:verify`, never `/verify`. Choose
the plugin `name` with that in mind: it is a permanent user-facing prefix on every
skill. Something short — `movian` — reads better than `movian-plugin-sdk`.

One unrelated collision rule, for completeness: *nested* project skills (a
`.claude/skills/` in a subdirectory) don't override — both stay available, the nested one
under a directory-qualified name like `apps/web:deploy`. [DOCS][skills-where]

### 5.3 Where this does not reach — an honest limit

`~/.claude/skills/` and user-scope plugins are **not** read by Cowork sessions or cloud
sessions/routines. [DOCS][skills-cloud] For those, a skill must either be enabled on the
claude.ai account, committed to the repo's `.claude/skills/`, or shipped in a plugin
declared in the **repository's** `.claude/settings.json` — *"plugins enabled only in
your user settings don't transfer."* [DOCS][skills-cloud]

So the zero-files-in-plugin-repos guarantee holds for **local** Claude Code sessions,
which is the stated target. If Movian plugin work ever moves to cloud sessions, the SDK
would have to be declared in each plugin repo's `.claude/settings.json` —
i.e. one file, unavoidably. Flagging this now rather than discovering it later.

---

## 6. Validation

`claude plugin validate <path>` checks both manifest kinds and is the practical stand-in
for the 404'd schema URL. Against the probe marketplace [TESTED]:

```
$ claude plugin validate /tmp/mp-test/sdk-probe
Validating marketplace manifest: /tmp/mp-test/sdk-probe/.claude-plugin/marketplace.json
⚠ Found 2 warnings:
  ❯ description: No marketplace description provided...
  ❯ plugins[0] plugin.json → author: No author information provided...
✔ Validation passed with warnings
```

It reaches *through* the marketplace entry into the referenced `plugin.json`, so one
invocation at the repo root covers both files. Worth wiring into CI — the openai
marketplace does exactly that
(`.../openai-codex/.github/workflows/pull-request-ci.yml`). [EXAMPLE]

Related tooling: `claude plugin details <name>` prints the component inventory and a
projected token cost (the probe plugin: `Always-on: ~30 tok added to every session`)
[TESTED]; `claude plugin init` scaffolds; `claude plugin tag` creates a
`{name}--v{version}` release tag, validating that `plugin.json` and the marketplace entry
agree.

---

## 7. Minimal working layout for `movian-plugin-sdk`

The smallest tree that delivers one skill to a session running in
`~/movian-plugin-HDRezka`. Four files:

```
movian-plugin-sdk/
├── .claude-plugin/
│   └── marketplace.json                      # makes the repo a marketplace
└── plugins/
    └── movian/
        ├── .claude-plugin/
        │   └── plugin.json                   # names the plugin → skill prefix
        └── skills/
            └── verify/
                └── SKILL.md                  # the delivered skill
```

`.claude-plugin/marketplace.json`:

```json
{
  "name": "movian-plugin-sdk",
  "owner": { "name": "Buksa" },
  "description": "Portable development layer for Movian plugins.",
  "plugins": [
    {
      "name": "movian",
      "description": "Movian plugin development: build, launch, verify.",
      "source": "./plugins/movian"
    }
  ]
}
```

`plugins/movian/.claude-plugin/plugin.json`:

```json
{
  "name": "movian",
  "description": "Movian plugin development: build, launch, verify.",
  "author": { "name": "Buksa" }
}
```

**`version` is deliberately omitted from both** — so every commit is a new version and
`claude plugin update` works without a manual bump (§3.2). [DOCS][mkt-version]

`plugins/movian/skills/verify/SKILL.md`:

```markdown
---
name: verify
description: This skill should be used when the user asks to "verify a Movian plugin", "smoke-test" a plugin change, or judge whether a Movian fix is proven.
---

# Verify a Movian plugin change

...
```

Consumption from `~/movian-plugin-HDRezka`, adding nothing to that repo:

```bash
claude plugin marketplace add Buksa/movian-plugin-sdk
claude plugin install movian@movian-plugin-sdk --scope user
# then, in a session: /reload-plugins
```

The skill is then invocable as **`/movian:verify`** from any repo on the machine, and
Claude can load it automatically from its `description`.

**Growth path from here, no restructuring required:** add more `skills/<name>/SKILL.md`
directories (auto-discovered, no manifest edit); add `agents/*.md`; add
`hooks/hooks.json`; add `.mcp.json`. All are auto-discovered at their default paths
(§2). Reference bundled scripts through `${CLAUDE_PLUGIN_ROOT}`, and keep every path
inside the plugin root — `../` escapes do not survive the cache copy. [DOCS][ref-caching]

**During development**, skip install entirely:

```bash
claude --plugin-dir ~/movian-plugin-sdk/plugins/movian
```

Same layout, no cache copy, no push (§4.3).

---

## 8. What could not be established

- **The published JSON schema.** `https://anthropic.com/claude-code/marketplace.schema.json`,
  cited as `$schema` by Anthropic's own official marketplace, returns **404**. [TESTED]
  The field is documented as ignored at load time. [DOCS][mkt-create] Field lists here
  come from the prose reference and from real manifests, not from a machine-readable
  schema. `plugin.json` has a different, `schemastore.org`-hosted `$schema` in the docs
  example, which was not fetched or verified.
- **Whether `#ref` works on a `directory` source.** It does not — `file://` is rejected
  outright [TESTED] — but no documentation states what happens for a plain relative path
  with a `#ref` suffix. Untested, and probably meaningless since a directory is used in
  place at whatever ref is checked out.
- **Precedence between two *plugins* that expose the same `plugin-name:skill-name`.**
  Two marketplaces each shipping a plugin named `movian` would collide in the namespace;
  no documentation was found on how that resolves. Not a live risk (the prefix is unique
  here), but unestablished.
- **The claim in §0 was verified structurally, not by a live session.** `claude plugin list`
  from `~/movian-plugin-HDRezka` showed the user-scope plugin, and that repo's `.claude/`
  holds no skills [TESTED] — but no interactive Claude session was started there to watch
  the skill be invoked. Delivery-by-scope is documented and the mechanism is consistent;
  the final end-to-end invocation is inferred, not observed.

---

## References

[mkt-create]: https://code.claude.com/docs/en/plugin-marketplaces
[mkt-entries]: https://code.claude.com/docs/en/plugin-marketplaces#plugin-entries
[mkt-sources]: https://code.claude.com/docs/en/plugin-marketplaces#plugin-sources
[mkt-version]: https://code.claude.com/docs/en/plugin-marketplaces#version-resolution-and-release-channels
[mkt-team]: https://code.claude.com/docs/en/plugin-marketplaces#require-marketplaces-for-your-team
[mkt-private]: https://code.claude.com/docs/en/plugin-marketplaces#private-repositories
[discover-how]: https://code.claude.com/docs/en/discover-plugins#how-marketplaces-work
[discover-add]: https://code.claude.com/docs/en/discover-plugins#add-marketplaces
[discover-install]: https://code.claude.com/docs/en/discover-plugins#install-plugins
[discover-manage]: https://code.claude.com/docs/en/discover-plugins#manage-installed-plugins
[discover-reload]: https://code.claude.com/docs/en/discover-plugins#apply-plugin-changes-without-restarting
[discover-autoupdate]: https://code.claude.com/docs/en/discover-plugins#configure-auto-updates
[plugin-schema]: https://code.claude.com/docs/en/plugins-reference#plugin-manifest-schema
[ref-skills]: https://code.claude.com/docs/en/plugins-reference#skills
[ref-layout]: https://code.claude.com/docs/en/plugins-reference#standard-plugin-layout
[ref-paths]: https://code.claude.com/docs/en/plugins-reference#path-behavior-rules
[ref-caching]: https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution
[ref-skillsdir]: https://code.claude.com/docs/en/plugins-reference#skills-directory-plugins
[ref-listing]: https://code.claude.com/docs/en/plugins-reference#plugin-list
[scopes]: https://code.claude.com/docs/en/plugins-reference#plugin-installation-scopes
[skills-where]: https://code.claude.com/docs/en/skills#where-skills-live
[skills-cloud]: https://code.claude.com/docs/en/skills#skills-in-cowork-and-cloud-sessions

- Marketplace guide — https://code.claude.com/docs/en/plugin-marketplaces
- Discover and install plugins — https://code.claude.com/docs/en/discover-plugins
- Plugins reference — https://code.claude.com/docs/en/plugins-reference
- Skills — https://code.claude.com/docs/en/skills
- Create plugins — https://code.claude.com/docs/en/plugins

Local evidence:

- `~/.claude/plugins/marketplaces/openai-codex/.claude-plugin/marketplace.json`
- `~/.claude/plugins/marketplaces/openai-codex/plugins/codex/.claude-plugin/plugin.json`
- `~/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json`
- `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/example-plugin/` (README, `skills/`, `commands/`)
- `~/.claude/plugins/known_marketplaces.json`
- `~/.claude/plugins/installed_plugins.json`
- `~/.claude/plugins/cache/openai-codex/codex/1.0.6/`
