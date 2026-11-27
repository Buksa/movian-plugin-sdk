// Movian's store proxy saves the value but its setter does not return true.

var http = require('movian/http');
var fs = require('fs');
var store = require('movian/store').create('account');
var storeFile = Core.storagePath + '/store/account'; // the file the store above reads and writes
var oauth = 'https://id.twitch.tv/oauth2/';
var deviceGrant = 'urn:ietf:params:oauth:grant-type:device_code';
var defaultClientId = 'm0zd4pbl3td7d0dk0jh9kxrpgn4vh5';
var session = store.session || null;
var checkedAt = 0;
var checking = false;

function request(url, options) {
    options.verifySSL = true;
    options.noFollow = true;
    options.noFail = true;
    options.noAuth = true;
    var response = http.request(url, options);
    var data;
    try { data = JSON.parse(response.toString()); } catch (e) { data = {}; } // proxies send HTML on 5xx
    return {status: response.statuscode, data: data};
}

function post(path, body) {
    return request(oauth + path, {method: 'POST', postdata: body});
}

function save(value) {
    store.session = value;
    session = value;
    checkedAt = 0;
    // The store writes 5 s later. Twitch kills the old refresh token on rotation, so losing
    // the new one on quit logs the user out: write the same file now.
    fs.writeFileSync(storeFile, JSON.stringify({clientId: store.clientId, session: value}));
}

exports.clientId = function() { return store.clientId || defaultClientId; };
exports.setClientId = function(value) {
    if ((value || defaultClientId) === exports.clientId()) return;
    store.clientId = value;
    save(null);
};
exports.login = function() { return session && session.login; };
// Sessions from before follows were supported have no userId and no follows scope.
exports.userId = function() { return session && session.userId; };
exports.logout = function() { save(null); };

exports.start = function(id) {
    var reply = post('device', {client_id: id, scopes: 'user:read:follows'});
    var data = reply.data;
    if (reply.status !== 200 || !data.device_code || !/^[A-Z0-9-]{4,16}$/i.test(data.user_code) ||
        !(data.expires_in > 0)) {
        throw new Error('Twitch не выдал код. Проверьте, что Client ID принадлежит приложению типа Public.');
    }
    return data;
};

exports.poll = function(id, code) {
    var reply;
    // Network and server failures are transient: keep polling until the code expires.
    try { reply = post('token', {client_id: id, device_code: code, grant_type: deviceGrant}); }
    catch (e) { return {status: 'authorization_pending'}; }
    if (reply.status >= 500) return {status: 'authorization_pending'};
    if (reply.status === 200) return {token: reply.data};
    var status = reply.data.error || reply.data.message;
    if (status === 'authorization_pending' || status === 'slow_down' || status === 'access_denied') {
        return {status: status};
    }
    if (reply.status === 429) return {status: 'slow_down'};
    throw new Error('Twitch отклонил код входа (HTTP ' + reply.status + '). Запросите новый код.');
};

function validate(id, accessToken) {
    var reply = request(oauth + 'validate', {headers: {Authorization: 'OAuth ' + accessToken}});
    if (reply.status === 401) return null;
    // An unreadable 200 must not look like a foreign token, or the session gets deleted.
    if (reply.status !== 200 || !reply.data.client_id) {
        throw new Error('Не удалось проверить сеанс Twitch (HTTP ' + reply.status + ').');
    }
    if (reply.data.client_id !== id || !reply.data.login) return null;
    return reply.data;
}

function sessionValue(id, login, token) {
    if (!token.access_token || !token.refresh_token || !(token.expires_in > 0)) {
        throw new Error('Twitch вернул неполный токен.');
    }
    return {clientId: id, login: login, accessToken: token.access_token,
        refreshToken: token.refresh_token, expires: Date.now() + Number(token.expires_in) * 1000};
}

function setToken(id, token) {
    var value = sessionValue(id, null, token);
    var identity = validate(id, value.accessToken);
    if (!identity) throw new Error('Twitch не подтвердил токен пользователя.');
    value.login = identity.login;
    value.userId = identity.user_id;
    return value;
}

exports.complete = function(id, token, active) {
    var value = setToken(id, token);
    if (!active() || id !== exports.clientId()) return false;
    save(value);
    checkedAt = Date.now();
    return true;
};

function refresh(value) {
    var reply = post('token', {grant_type: 'refresh_token', client_id: value.clientId,
        refresh_token: value.refreshToken});
    if (session !== value) return null;
    if (reply.status === 400 || reply.status === 401) {
        save(null);
        return null;
    }
    if (reply.status !== 200) throw new Error('Не удалось обновить вход Twitch (HTTP ' + reply.status + ').');
    // Store the rotated refresh token before doing any further network I/O.
    var fresh = sessionValue(value.clientId, value.login, reply.data);
    fresh.userId = value.userId;
    save(fresh);
    return fresh;
}

function credentials(force) {
    var value = session;
    if (!value) return null;
    var now = Date.now();
    if (!force && value.expires > now + 60000 && now - checkedAt < 3600000) return value;
    if (checking) {
        // Another page is checking the session; a token that has not expired is still usable.
        if (value.expires > now) return value;
        throw new Error('Проверка входа Twitch уже идёт. Откройте каталог ещё раз.');
    }
    checking = true;
    try {
        if (force || value.expires <= now + 60000) value = refresh(value);
        if (!value) return null;
        var identity = validate(value.clientId, value.accessToken);
        if (session !== value) return null;
        if (!identity || identity.login !== value.login) {
            save(null);
            return null;
        }
        checkedAt = Date.now();
        return value;
    } finally {
        checking = false;
    }
}

exports.catalog = function(path, filters, cursor) {
    var args = {first: 24};
    Object.keys(filters).forEach(function(key) { args[key] = filters[key]; });
    if (cursor) args.after = cursor;
    function fetch(value) {
        return request('https://api.twitch.tv/helix/' + path, {args: args,
            headers: {'Client-Id': value.clientId, Authorization: 'Bearer ' + value.accessToken}});
    }
    var value = credentials(false);
    if (!value) return null;
    var reply = fetch(value);
    if (session !== value) return null;
    if (reply.status === 401) {
        value = credentials(true);
        if (!value) return null;
        reply = fetch(value);
        if (session !== value) return null;
    }
    if (reply.status !== 200 || !Array.isArray(reply.data.data)) {
        throw new Error('Не удалось загрузить каталог Helix (HTTP ' + reply.status + ').');
    }
    return {nodes: reply.data.data, next: reply.data.pagination && reply.data.pagination.cursor};
};
