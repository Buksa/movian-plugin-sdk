// The Movian store proxy's setter does not return true; write outside strict mode.
var store = require('movian/store').create('playback');

exports.remember = function(item) {
    var saved = store.quality;
    if (saved && saved.label === item.label && saved.height === item.height && saved.fps === item.fps) return;
    store.quality = {label: item.label, height: item.height, fps: item.fps};
};

exports.initial = function(choices) {
    var saved = store.quality;
    if (!saved || !saved.height) return choices.initial;
    // Both Twitch providers sort variants by descending height, then FPS.
    var fallback = -1;
    var sameRate = -1;
    for (var i = 0; i < choices.items.length; i++) {
        var item = choices.items[i];
        if (item.height === saved.height && item.label === saved.label) return i;
        if (sameRate < 0 && item.height === saved.height && item.fps === saved.fps) sameRate = i;
        if (fallback < 0 && item.height <= saved.height) fallback = i;
    }
    if (sameRate >= 0) return sameRate;
    if (fallback >= 0) return fallback;
    var last = choices.items.length - 1;
    while (last > 0 && choices.items[last - 1].height === choices.items[last].height) last--;
    return last;
};
