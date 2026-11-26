'use strict';

var fap = require('native/faprovider');
var http = require('movian/http');
var protocol = 'smarttwitch-media';
var suffix = '/live.m3u8';
var cdn = /^https:\/\/(?:[a-z0-9-]+\.)+(?:ttvnw\.net|cloudfront\.net|jtvnw\.net)\/[!-~]+$/i;
// Movian's TS-only HLS engine recognizes tags in the first 1 KiB. Put the
// variant after that so libavformat handles both CMAF and MPEG-TS playlists.
var masterPrefix = '#EXTM3U\n#' + new Array(1025).join(' ') + '\n';

function playlist(path) {
    var match = /^(\d+)\/([^/]+)\/live\.m3u8$/.exec(path);
    if (!match) throw new Error('Неверный адрес эфира Twitch.');
    var variant = decodeURIComponent(match[2]);
    if (!cdn.test(variant)) throw new Error('Неверный CDN эфира Twitch.');
    return masterPrefix + '#EXT-X-STREAM-INF:BANDWIDTH=' + match[1] + '\n' + variant + '\n';
}

fap.register(protocol, {
    open: function(handle, path) {
        try {
            var text = playlist(path);
            var bytes = new Uint8Array(text.length);
            for (var i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
            fap.setSize(handle, bytes.length);
            fap.openRespond(handle, true, bytes);
        } catch (e) {
            fap.openRespond(handle, false, e.message);
        }
    },
    stat: function(handle, path) {
        try {
            fap.statRespond(handle, true, playlist(path).length, 'file', 0);
        } catch (e) {
            fap.statRespond(handle, false, e.message);
        }
    },
    read: function(handle, bytes, out, size, offset) {
        var count = Math.max(0, Math.min(size, bytes.length - offset));
        if (count) out.set(bytes.subarray(offset, offset + count));
        fap.readRespond(handle, count);
    },
    close: function(handle) { fap.closeRespond(handle); }
});

exports.variants = function(master, isLive) {
    var response = http.request(master, {verifySSL: true, compression: true, noFail: true});
    if (response.statuscode !== 200) throw new Error('Плейлист Twitch недоступен (HTTP ' + response.statuscode + ').');
    var lines = response.toString().split(/\r?\n/);
    var variants = [];
    var seen = Object.create(null);
    for (var i = 0; i + 1 < lines.length; i++) {
        var line = lines[i];
        if (line.indexOf('#EXT-X-STREAM-INF:') !== 0 || !/\bavc1\./i.test(line)) continue;
        var resolution = /\bRESOLUTION=\d+x(\d+)/.exec(line);
        var bandwidth = /\bBANDWIDTH=(\d+)/.exec(line);
        var group = /\bVIDEO="([^"]+)"/.exec(line);
        var candidate = lines[i + 1].trim();
        if (!resolution || !bandwidth || !cdn.test(candidate)) continue;
        var height = Number(resolution[1]);
        var rate = /\bFRAME-RATE=([\d.]+)/.exec(line);
        var groupRate = group && /^\d+p(\d+)$/.exec(group[1]);
        var fps = rate ? Math.round(Number(rate[1])) : (groupRate ? Number(groupRate[1]) : 0);
        var label = height + 'p' + (fps ? fps : '');
        if (group && group[1] === 'chunked') label = 'Источник · ' + label;
        if (seen[label]) continue;
        seen[label] = true;
        var bitrate = Math.max(1, Number(bandwidth[1]));
        variants.push({label: label, height: height, fps: fps, bitrate: bitrate,
            url: protocol + '://' + bitrate + '/' + encodeURIComponent(candidate) + suffix});
    }
    if (!variants.length) throw new Error('Twitch не предоставил совместимый вариант H.264.');
    variants.sort(function(a, b) { return b.height - a.height || b.fps - a.fps || b.bitrate - a.bitrate; });
    var initial = 0;
    if (isLive) {
        while (initial + 1 < variants.length && variants[initial].height > 720) initial++;
        while (initial > 0 && variants[initial - 1].height === variants[initial].height) initial--;
    }
    return {items: variants, initial: initial};
};
