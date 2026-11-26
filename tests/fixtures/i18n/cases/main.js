// Fixture for tests/i18n_extract_selftest.js. "SHOW" strings must be listed,
// "KEEP" strings must not be listed as candidates (most must not be listed at all).
var page = require('movian/page/KEEP require path');
var settings = require('movian/settings');
var popup = require('native/popup');
var http = require('movian/http');
var t = require('./i18n').t;
var base = 'https://example.com/KEEP url';
var defaults = {quality: 'KEEP stored value'};

var prefs = new settings.globalSettings('plugin', 'SHOW settings title', 'logo.png', 'SHOW settings description');
prefs.createString('server', 'SHOW server address', 'KEEP setting default', function() {});

function status(page, message) { page.metadata.detail = message; }

new page.Route('plugin:start:(.*)', function(page) {
    console.log('KEEP log line');
    print('KEEP print line');
    trace('KEEP trace line');
    page.metadata.glwview = Plugin.path + 'views/main.view';
    page.metadata.title = 'SHOW page title';
    page.metadata.mode = 'video';
    page.onEvent('KeepEventName', function() {});
    var reply = http.request(base, {headers: {'User-Agent': 'KEEP user agent (X11; Linux)'}});
    if (reply.statuscode === 'KEEP compared value') return;
    switch (page.metadata.mode) { case 'KEEP switch case': break; }
    var keys = {'KEEP property key': 1};
    var value = keys['KEEP computed key'];
    if (/KEEP regex/.test(value) || new RegExp('KEEP regexp source').test(value)) return;
    page.appendItem('plugin:item:1', 'video', {title: 'SHOW item title', icon: 'keep-icon.png'});
    page.appendAction('SHOW action title', function() {});
    popup.notify('SHOW notice', 2);
    status(page, 'SHOW through local function');
    page.metadata.notice = 'SHOW concatenation: ' + value;
    page.metadata.notice = t('SHOW already translated');
    if (!reply) throw new Error('SHOW error message');
    defaults.quality = value === defaults.quality ? 'KEEP stored value' : value;
});
