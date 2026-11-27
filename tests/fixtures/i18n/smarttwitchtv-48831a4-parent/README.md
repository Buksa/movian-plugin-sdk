# STT for Movian (formerly SmartTwitchTV) before its i18n commit

A copy of the plugin's JS, views and `plugin.json` from
https://github.com/Buksa/movian-plugin-stt at the parent of commit
[48831a4](https://github.com/Buksa/movian-plugin-stt/commit/48831a4)
("Add English and Russian UI text"). `tests/i18n_extract_selftest.js` checks that
`extract` finds every string that commit translated. It is copied, not fetched,
so the test runs offline.

Reproduce: `git -C <clone> archive 48831a4^ -- '*.js' views plugin.json ':!test'`.
