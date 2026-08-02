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

## `plugin-findings/`

Also rescued by [#13](https://github.com/Buksa/movian-plugin-sdk/issues/13), from
the same untracked directory.

`anilibria-review-vs-hdrezka.md` is a review of `movian-plugin-anilibria` against
the Movian ecmascript API sources and HDRezka as reference implementation. It
reports **4 bugs (2 critical) and 9 code-quality issues** — `page.redirect()`
called on the module object, a non-existent `apiUrlSetting.set()`, a schedule
response-format mismatch, an invalid sorting value.

**None of it is verified**, and fixing plugins is out of this map's scope. It is
kept because `movian-plugin-anilibria` has no remote and therefore no issue
tracker, so this file is the only record. Once
[Where is plugin work tracked?](https://github.com/Buksa/movian-plugin-sdk/issues/6)
decides where plugin work lives, these findings belong there — verified first.
