'use strict';

var account = require('./account');
var prop = require('movian/prop');
var popup = require('native/popup');
var activeLogin;

module.exports = function(page) {
    var timer;
    function cancel() {
        if (activeLogin === cancel) activeLogin = null;
        if (timer !== undefined) {
            clearTimeout(timer);
            timer = undefined;
        }
        if (!prop.isZombie(page.root)) page.metadata.accountCode = null;
    }
    function active() { return activeLogin === cancel && !prop.isZombie(page.root); }
    function status(message) { page.metadata.detail = message; }
    function action(label, handler) {
        page.appendAction(label, function() {
            try { handler(); }
            catch (e) { cancel(); if (!prop.isZombie(page.root)) status(e.message || String(e)); }
        });
    }
    if (activeLogin) activeLogin();
    status(account.login() ? 'Вы вошли как ' + account.login() : 'Войдите, чтобы открыть полный каталог категорий.');
    page.onEvent('TwitchCancelLogin', function() {
        if (!active()) return;
        cancel();
        status('Вход по коду отменён.');
    });
    action('Войти по коду', function() {
        var id = account.clientId();
        if (activeLogin) activeLogin();
        activeLogin = cancel;
        status('Запрашиваем код у Twitch…');
        var challenge = account.start(id);
        if (!active()) return;
        var expires = Date.now() + challenge.expires_in * 1000;
        var interval = Math.max(5, Number(challenge.interval) || 5);
        page.metadata.accountCode = challenge.user_code;
        status('На телефоне откройте twitch.tv/activate?public=true и введите код.');
        function tick() {
            if (!active()) return;
            timer = undefined;
            try {
                if (Date.now() >= expires) throw new Error('Код истёк. Запросите новый.');
                var result = account.poll(id, challenge.device_code);
                if (!active()) return;
                if (result.token) {
                    if (!account.complete(id, result.token, active)) return;
                    cancel();
                    status('Вы вошли как ' + account.login() + '. Откройте «Категории».');
                    return;
                }
                if (result.status === 'access_denied') throw new Error('Вход отклонён.');
                if (result.status === 'slow_down') interval += 5;
                timer = setTimeout(tick, interval * 1000);
            } catch (e) {
                if (active()) { cancel(); status(e.message || String(e)); }
            }
        }
        timer = setTimeout(tick, interval * 1000);
    });
    action('Настроить Public Client ID', function() {
        var answer = popup.textDialog('Public Client ID (пустое поле — использовать встроенный)', true, true);
        if (answer.rejected) return;
        var id = String(answer.input || '').trim();
        if (id && !/^[a-z0-9]{20,64}$/i.test(id)) { status('Укажите Public Client ID, не секрет.'); return; }
        cancel();
        account.setClientId(id);
        status(account.login() ? 'Вы вошли как ' + account.login() : 'Выберите «Войти по коду».');
    });
    action('Выйти / отменить вход', function() {
        cancel();
        account.logout();
        status('Аккаунт Twitch отключён.');
    });
};
