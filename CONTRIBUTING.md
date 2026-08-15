# Contributing to the canon

## The rule that decides where something goes

**Sort by audience. One home per line. Never duplicate.**

Content whose reader is a **plugin developer** lives here. Content whose reader
is a **core developer** lives in [buksa/movian](https://github.com/buksa/movian).
The core repo installs the `movian` plugin, so it keeps the shared half without a
second copy. This is the structural cure for drift — there is no sync step to
forget, because there is nothing to sync.

One deliberate exception: **documentation of the core's own API surface stays
beside the code it describes**, even though plugin developers read it. Moving
`PLUGIN_API_REFERENCE.md` away from the C it documents would trade one drift for
a worse one. It is *delivered* instead — the `movian:api` skill routes to it
through the locator.

## The channel rule

Every canon item must declare which of the two delivery channels it rides.

| channel | carries | how it reaches a repo |
|---|---|---|
| **Marketplace** | markdown skills | `plugins/movian/skills/<name>/SKILL.md`, auto-discovered, namespaced `movian:<name>`, user scope, **zero files added** to the target repo |
| **`install.sh`** | executables on `PATH` | `bin/`, `lib/` — a plugin ships skills, not binaries |

If you are adding something that must be *run* rather than *read*, it is the
second channel, and the marketplace cannot deliver it. That is not a limitation
to work around; it is why `install.sh` exists.

## Skills

```
plugins/movian/skills/<name>/
  SKILL.md
  references/*.md      # optional, loaded on demand
```

The `name` in the frontmatter becomes `movian:<name>`. Keep it short — the plugin
name is already a permanent prefix.

Write `description` so it names the **triggers**: what the user asks that should
pull this skill in. It is the only part loaded into every session, so it earns
its tokens by routing accurately, not by summarising.

Never assume the core checkout is the cwd. Anything reaching into the core goes
through `$(mdev core)`; anything runnable goes through `mdev`, which resolves the
core itself.

## Iterating

Installed plugins are served from a **versioned cache**, so editing this working
tree changes nothing a session sees. Iterate with:

```
claude --plugin-dir "$PWD/plugins/movian"
```

and install for real use. After pushing, `claude plugin update movian@movian-plugin-sdk`
picks the change up — every commit is a new version, which is why `version` is
deliberately absent from both manifests.

Validate before pushing:

```
claude plugin validate .
```

The warning about a missing `version` is expected.

## `tests/`

Checks for the `install.sh` channel — the parts that are run rather than read.
Not installed; run from the checkout.

```
python3 tests/typefloor_selftest.py --dts "$(mdev core)/generated/movian-api.d.ts"
```

It needs a core whose artifact currently passes, and says so if given one that
does not. Anything added here should be able to **fail** for a stated reason:
this suite exists because `mdev types` now makes a claim about the core's
artifact, and a claim nothing can falsify is the bug it was written to prevent.

## `salvage/`

Staging for content rescued from untracked machine state. It sits outside
`plugins/movian/`, so **nothing there is delivered**. Adapt it into a skill, then
delete it from `salvage/`.
