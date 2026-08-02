# salvage/

Content rescued verbatim from untracked machine state. **Nothing here is
delivered to any session** — it sits outside `plugins/movian/`, so the
marketplace does not discover it.

It is staged here so it exists in version control at all, and adapted into
`plugins/movian/skills/` by the canon split
([#14](https://github.com/Buksa/movian-plugin-sdk/issues/14)). Delete each item
from here once its adapted form lands.

## `mimocode-skills/` — cleared

Held `mdev-plugin-testing` (369 lines, Mimo format). Resolved by
[#14](https://github.com/Buksa/movian-plugin-sdk/issues/14): its genuinely new
material — test recipes per plugin type — became
`plugins/movian/skills/verify/references/plugin-type-patterns.md`. The rest
duplicated the `movian:run` loop and was deliberately not carried over.

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
