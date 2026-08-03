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

## `plugin-findings/` — cleared

Held the anilibria review. Resolved by
[#17](https://github.com/Buksa/movian-plugin-sdk/issues/17): the local anilibria
turned out to be a **separate plugin** (`id: anilibria`) rather than a version of
`Buksa/movian-plugin-anilibria.tv` (`id: anilibria.tv`), and now lives as the
`Buksa/single-file-plugin` branch of that repo. The review went with it as
`docs/review-vs-hdrezka.md`, marked historical — its findings were already fixed
by the commits it motivated.

`salvage/` is now empty of content; it stays for the next rescue.
