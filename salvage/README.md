# salvage/

Content rescued verbatim from untracked machine state. **Nothing here is
delivered to any session** — it sits outside `plugins/movian/`, so the
marketplace does not discover it.

It is staged here so it exists in version control at all, and adapted into
`plugins/movian/skills/` by the canon split
([#14](https://github.com/Buksa/movian-plugin-sdk/issues/14)). Delete each item
from here once its adapted form lands.

## `mimocode-skills/`

Rescued by [#13](https://github.com/Buksa/movian-plugin-sdk/issues/13). These are
**Mimo-format** skills (`.mimocode/skills/`), not Claude skills — they were
tracked in no repository at all and existed in exactly one ephemeral Orca
worktree.

| skill | lines | note |
|---|---|---|
| `mdev-plugin-testing` | 369 | the plugin-facing one; the other six were plugin-agnostic pipeline skills and went to the core repo instead, per [#4](https://github.com/Buksa/movian-plugin-sdk/issues/4) |

Adapting it is #14's job: it is written for the Mimo runtime and assumes a core
checkout as cwd, which the locator contract has since replaced.
