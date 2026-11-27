#!/usr/bin/env node
// Checks lib/i18n/extract.js against two fixtures:
//   cases/                         one case per rule: SHOW strings are listed, KEEP strings are not
//   smarttwitchtv-48831a4-parent/  SmartTwitchTV just before its English/Russian commit 48831a4:
//                                  the tool must find every string that commit translated.
//                                  Copied, so the test runs offline, from
//                                  https://github.com/Buksa/movian-plugin-twitchtv at the parent of
//                                  https://github.com/Buksa/movian-plugin-twitchtv/commit/48831a4
// Views need the core's movian-analyze (`mdev core`); without it the view half is SKIPPED, said so.
// Run: (cd lib/i18n && npm ci) && node tests/i18n_extract_selftest.js
'use strict';
var assert = require('assert');
var fs = require('fs');
var path = require('path');
var extract = require('../lib/i18n/extract').extract;

var fixtures = path.join(__dirname, 'fixtures', 'i18n');
var views = true;
function run(dir) {
    try { return extract(path.join(fixtures, dir)); } catch (e) {
        if (!/mdev core|movian-analyze/.test(e.message)) throw e;
        console.log('SKIP views: ' + e.message);
        views = false;
        // Same plugin without its views, so the JS half still runs.
        var tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'i18n-'));
        fs.readdirSync(path.join(fixtures, dir)).filter(function(f) { return f.endsWith('.js'); }).forEach(function(f) {
            fs.copyFileSync(path.join(fixtures, dir, f), path.join(tmp, f));
        });
        return extract(tmp);
    }
}

// --- one case per rule
var report = run('cases');
var byText = {};
report.entries.forEach(function(e) { (byText[e.text] = byText[e.text] || []).push(e); });
function status(text) {
    assert.ok(byText[text], 'not listed: ' + text);
    return byText[text].map(function(e) { return e.status; }).join(' | ');
}
var expected = {
    'SHOW settings title': 'flag: module-load',
    'SHOW settings description': 'flag: module-load',
    'SHOW server address': 'flag: module-load',
    'SHOW page title': 'candidate',
    'SHOW item title': 'candidate',
    'SHOW action title': 'candidate',
    'SHOW notice': 'candidate',
    'SHOW through local function': 'candidate',
    'SHOW concatenation: %s': 'flag: concatenation',
    'SHOW already translated': 'flag: already-localized',
    'SHOW error message': 'flag: error-message'
};
if (views) {
    Object.assign(expected, {
        'SHOW caption': 'candidate',
        'SHOW rich text': 'candidate',
        'SHOW grid view': 'candidate',
        'SHOW list view': 'candidate',
        'SHOW channels: ': 'candidate',
        'SHOW macro title': 'candidate',
        'SHOW unknown macro argument': 'flag: unknown-macro',
        'SHOW core catalog': 'flag: already-localized',
        'SHOW english': 'flag: already-localized',
        'SHOW русский': 'flag: already-localized'
    });
}
Object.keys(expected).forEach(function(text) { assert.strictEqual(status(text), expected[text], text); });
report.entries.forEach(function(e) {
    if (!/KEEP/.test(e.text)) return;
    // A stored value cannot be told from text by looking; it may be listed for review, never as a candidate.
    assert.ok(e.text === 'KEEP stored value' && /no-sink/.test(e.status), 'listed: ' + JSON.stringify(e));
});
assert.strictEqual(byText['SHOW concatenation: %s'][0].placeholders[0], 'value');
var page = byText['SHOW page title'][0];
var source = fs.readFileSync(path.join(fixtures, 'cases', 'main.js'), 'utf8');
assert.strictEqual(source.slice(page.span[0], page.span[1]), "'SHOW page title'", 'JS span');
if (views) {
    var rich = byText['SHOW rich text'][0];
    var view = fs.readFileSync(path.join(fixtures, 'cases', 'views', 'main.view'), 'utf8');
    assert.strictEqual(view.slice(rich.span[0], rich.span[1]), "'SHOW rich text'", 'view span');
    assert.ok(/rich text/.test(rich.sink));
}
assert.ok(!report.notes.some(function(n) { return /already localized/.test(n); }), 'cases is not localized');

// --- SmartTwitchTV before 48831a4: every string the commit translated
var translated = [
    // account-page.js
    'Вы вошли как ', 'Войдите, чтобы открыть полный каталог категорий.', 'Вход по коду отменён.', 'Войти по коду',
    'Запрашиваем код у Twitch…', 'На телефоне откройте twitch.tv/activate?public=true и введите код.',
    'Код истёк. Запросите новый.', '. Откройте «Категории».', 'Вход отклонён.', 'Настроить Public Client ID',
    'Public Client ID (пустое поле — использовать встроенный)', 'Укажите Public Client ID, не секрет.',
    'Выберите «Войти по коду».', 'Выйти / отменить вход', 'Аккаунт Twitch отключён.',
    // account.js
    'Twitch не выдал код. Проверьте, что Client ID принадлежит приложению типа Public.',
    'Twitch отклонил код входа (HTTP ', 'Не удалось проверить сеанс Twitch (HTTP ', 'Twitch вернул неполный токен.',
    'Twitch не подтвердил токен пользователя.', 'Не удалось обновить вход Twitch (HTTP ',
    'Проверка входа Twitch уже идёт. Откройте каталог ещё раз.', 'Не удалось загрузить каталог Helix (HTTP ',
    // live.js
    'Неверный адрес эфира Twitch.', 'Неверный CDN эфира Twitch.', 'Плейлист Twitch недоступен (HTTP ',
    'Источник · ', 'Twitch не предоставил совместимый вариант H.264.',
    // main.js
    'Канал добавлен в избранное', 'Канал удалён из избранного', 'В эфире', 'Канал: ', 'Категория: ',
    'Сеанс Twitch завершён. Войдите заново.', 'В этом разделе пока ничего нет.', 'Для следующих страниц войдите в Twitch.',
    'Поиск Twitch: ', 'Ничего не найдено.', 'Канал, категория или ссылка Twitch', 'Прямые эфиры', 'Категории Twitch',
    'Аккаунт Twitch', 'Избранные каналы', 'Войдите заново, чтобы показать подписки Twitch.',
    'Добавьте канал в избранное на его странице.', 'Сейчас не в эфире', 'Записи', 'Клипы', 'Добавить в избранное',
    'Убрать из избранного', 'Трансляции', 'Откройте трансляцию на странице канала.',
    // twitch.js
    'Не удалось подключиться к Twitch: ', 'Twitch вернул HTTP ', 'Ошибка API Twitch', 'Неизвестный раздел Twitch.',
    'Канал или категория не найдены.', 'Канал Twitch не найден.', 'Категория Twitch не найдена.',
    'Twitch не выдал разрешение на просмотр.', 'Канал сейчас не в эфире.', 'Запись Twitch удалена или недоступна.',
    'Запись Twitch', 'Клип Twitch удалён или недоступен.', 'Клип недоступен для просмотра.', 'Клип Twitch'
];
if (views) {
    translated = translated.concat([
        '← Меню   ·   OK Открыть', ' просмотров', 'Каналы: ', 'Зрители: ', ' зрителей', 'Загрузка Twitch…',
        'Аккаунт Twitch', 'Поиск', 'Избранное', 'Прямые эфиры', 'Категории', 'Записи', 'Клипы', '→ Закрыть меню',
        'Открыть канал', 'Открыть категорию', 'Качество: ', 'Качество видео', '← Назад в плеер'
    ]);
}
var stv = run('smarttwitchtv-48831a4-parent');
var texts = stv.entries.map(function(e) { return e.text; });
var missed = translated.filter(function(s) { return !texts.some(function(text) { return text.indexOf(s) >= 0; }); });
assert.deepStrictEqual(missed, [], 'not found');
// The commit left this console line untranslated (only made English): it is a log, not UI.
assert.ok(!texts.some(function(text) { return /статистика категорий/.test(text); }), 'log line listed');
// Listed but not translated by the commit: the brand name, three times. Anything new here is a new false positive.
var extra = stv.entries.filter(function(e) { return !/[а-яё]/i.test(e.text); }).map(function(e) { return e.text; });
assert.deepStrictEqual(extra.sort(), (views ? ['SmartTwitchTV', 'SmartTwitchTV', 'Twitch'] : ['SmartTwitchTV']).sort());

console.log('ok: ' + report.entries.length + ' case entries, ' + stv.entries.length + ' SmartTwitchTV entries' +
    (views ? '' : ' (views SKIPPED)'));
