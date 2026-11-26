# Plugin i18n: `extract`

Lists a Movian plugin's user-visible strings (JS and GLW views) for a person to
review before they are translated the way SmartTwitchTV does it (its
`docs/i18n.md`): `t('English')` in JS with translations in `lang/<code>.lang`,
and in views text by id, `L(key)` reading `$self.model.metadata.i18n`. `extract`
changes nothing: plugin JS is parsed, never run, and nothing is written into the
plugin. The rewrite (`apply`) is a later step.

```
(cd lib/i18n && npm ci)                       # Acorn, pinned; the plugin gets no dependency
node lib/i18n/extract.js extract <plugin-dir>         # readable table
node lib/i18n/extract.js extract <plugin-dir> --json  # same, as JSON
```

Views need the core's GLW lexer: `$(mdev core)/build.debug/movian-analyze`
(`make BUILD=debug movian-analyze` in the core). Without it a plugin that has
views fails with that message, rather than listing only half of its strings.

## Each entry

| field | meaning |
|---|---|
| `file`, `line`, `col` | where the string starts; `col` is 1-based |
| `span` | `[start, end)` offsets in the file as JS reads it (UTF-16), quotes included; `null` for a view string the line search could not place (escapes, multi-line) |
| `text` | the string; a JS concatenation is shown as one template, `'Channel: ' + name` → `Channel: %s` |
| `sink` | how it reaches the screen, e.g. `status(#0) → metadata.detail`, `NAV(#1) → caption`; `(rich text)` for single-quoted GLW strings |
| `placeholders` | for a concatenation the joined expressions (`name`); otherwise `%s`-style codes already in the text |
| `status` | `candidate`, or `flag: …` listing the reasons it needs a person |

Flags:

- `concatenation` — JS built from pieces. Rewrite as one `t('… %s …', arg)` sentence. (In views a `"Channels: " + $x` caption is a plain candidate: a label id plus the value, `L(channels) + " " + $x`, is the view pattern.)
- `error-message` — passed to `new Error()`. Often shown by the route's error page, sometimes only logged or compared.
- `module-load` — runs when the plugin loads, before Movian sets the language: settings titles, tables of labels. `t()` cannot go here; keep the English key and translate where it is used.
- `unknown-macro` — an argument of a GLW macro the plugin's views do not define (a skin macro, usually): label or id, nobody can tell from here.
- `no-sink` — reads like a sentence but no known sink was found (cross-file tables, stored values, custom log helpers).
- `already-localized` — inside `t()`/`_()`, or a view macro that reads `i18n` (`L()`, an older `T()`), or the whole plugin localizes already (`Core.getString`, reads `i18n.iso639_1`, its own UI-language setting, ships `.lang` files). Do not rewrite such a plugin; see the note at the top of the report.

A note also says when strings are not in English: the English keys must then be written by hand.

## Limits

- Flow is followed inside one file: through local functions, variables, return values and `table[key]` lookups, by name rather than by scope. Strings that reach the screen through another module (`require('./strings')`) are `no-sink` at best.
- A stored or compared value that is also shown (SmartTwitchTV's quality label) cannot be told apart by reading; the apply step must not trust a `candidate` there blindly.
- Macros from every view are visible to every view.
- Template literals are not read (Duktape is ES5).
