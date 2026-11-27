'use strict';

var pages = require('movian/page');
var service = require('movian/service');
var popup = require('native/popup');
var favorites = require('movian/store').create('favorites');
var twitch = require('./twitch');
var live = require('./live');
var quality = require('./quality');
var account = require('./account');
var accountPage = require('./account-page');
var prefix = 'smarttwitchtv:';
var title = 'SmartTwitchTV';
var icon = Plugin.path + 'logo.svg';
var loginPattern = '[A-Za-z0-9_]{1,25}';
var slugPattern = '[A-Za-z0-9_-]+';

function url(path, key) {
    return prefix + path + (key === undefined ? '' : ':' + encodeURIComponent(key));
}

function directory(page, name, section, mode, image) {
    page.type = 'raw';
    page.loading = true;
    page.metadata.glwview = Plugin.path + 'views/catalog.view';
    page.metadata.title = name;
    page.metadata.section = section;
    page.metadata.mode = mode;
    if (image) page.metadata.logo = image;
    page.onEvent('TwitchSearch', function() {
        var query = input();
        if (query) page.redirect(destination(query));
    });
}

function link(page, path, name, key, image, description) {
    var metadata = {title: name};
    if (image) metadata.icon = image;
    if (description) metadata.description = description;
    return page.appendItem(url(path, key), 'directory', metadata);
}

function art(url, width, height) {
    return (url || '').replace(/%?\{width\}/, width).replace(/%?\{height\}/, height);
}

function label(page, name) {
    page.appendPassiveItem('label', null, {title: name});
}

function route(pattern, handler) {
    new pages.Route(prefix + pattern, function(page, a, b, c) {
        page.loading = true; // some routes fetch before directory() sets up the page
        try {
            handler(page, a, b, c);
            page.loading = false;
        } catch (e) {
            page.error(e.message || String(e));
        }
    });
}

function savedChannels() {
    return favorites.channels || [];
}

function favoriteIndex(channels, login) {
    for (var i = 0; i < channels.length; i++) {
        if (channels[i].login === login) return i;
    }
    return -1;
}

function toggleFavorite(user) {
    var channels = savedChannels().slice();
    var index = favoriteIndex(channels, user.login);
    if (index < 0) {
        channels.push({login: user.login, displayName: user.displayName, profileImageURL: user.profileImageURL});
        popup.notify('Канал добавлен в избранное', 2);
    } else {
        channels.splice(index, 1);
        popup.notify('Канал удалён из избранного', 2);
    }
    favorites.channels = channels;
}

function channelItem(page, user) {
    var item = link(page, 'channel', user.displayName || user.login, user.login, user.profileImageURL,
                    user.stream && 'В эфире');
    item.root.metadata.kind = 'channel';
    if (user.stream) item.root.metadata.live = true;
    return item;
}

function gameStat(value) {
    return typeof value === 'number' ? String(value).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0') : '';
}

function categoryItem(page, game) {
    var item = link(page, 'category', game.displayName || game.slug, game.slug, game.boxArtURL);
    item.root.metadata.kind = 'game';
    item.root.metadata.channels = gameStat(game.channelsCount);
    item.root.metadata.viewers = gameStat(game.viewersCount);
    return item;
}

function videoItem(page, kind, id, name, image, owner, node) {
    var metadata = {title: name || owner || id, kind: kind};
    if (image) metadata.icon = image;
    if (owner) metadata.artist = owner;
    if (node.language) metadata.language = node.language.toUpperCase();
    var duration = node.lengthSeconds || node.durationSeconds;
    if (duration > 0) metadata.duration = Math.floor(duration);
    var count = kind === 'live' ? node.viewersCount : node.viewCount;
    if (typeof count === 'number') metadata.count = count;
    if (node.game && node.game.name) metadata.game = node.game.name;
    var started = kind === 'live' && Date.parse(node.createdAt);
    if (started > 0) metadata.started = Math.floor(started / 1000);
    return page.appendItem(url('play:' + kind, id), 'video', metadata);
}

function streamItem(page, stream, user) {
    user = user || stream.broadcaster;
    if (!user || !user.login) return;
    var name = user.displayName || user.login;
    var item = videoItem(page, 'live', user.login, stream.title, stream.previewImageURL, name, stream);
    var channelUrl = url('channel', user.login);
    item.root.metadata.channelUrl = channelUrl;
    item.addOptURL('Канал: ' + name, channelUrl);
    if (stream.game && stream.game.slug) {
        var categoryUrl = url('category', stream.game.slug);
        item.root.metadata.categoryUrl = categoryUrl;
        item.addOptURL('Категория: ' + stream.game.name, categoryUrl);
    }
}

function listItem(page, kind, node) {
    if (kind === 'streams') {
        streamItem(page, node);
    } else if (kind === 'channels') {
        channelItem(page, node);
    } else if (kind === 'games') {
        if (node.slug) categoryItem(page, node);
    } else if (kind === 'videos' && node.id) {
        var thumb = art(node.previewThumbnailURL, 640, 360);
        videoItem(page, 'vod', node.id, node.title, thumb, node.owner && node.owner.displayName, node);
    } else if (kind === 'clips' && node.slug) {
        videoItem(page, 'clip', node.slug, node.title, node.thumbnailURL, node.broadcaster && node.broadcaster.displayName, node);
    }
}

function attachCatalog(page, kind, batch, load) {
    var seen = Object.create(null);
    var cursors = Object.create(null);
    var cursor;
    function append(current) {
        var added = false;
        current.nodes.forEach(function(node) {
            var key = kind === 'streams' ? node.broadcaster && node.broadcaster.login : kind === 'channels' ? node.login :
                (kind === 'clips' || kind === 'games' ? node.slug : node.id);
            if (!key || seen[key]) return;
            seen[key] = true;
            listItem(page, kind, node);
            added = true;
        });
        cursor = current.next;
        return added;
    }
    function advance() {
        while (cursor && !cursors[cursor]) {
            cursors[cursor] = true;
            var next = load(cursor);
            if (!next) throw new Error('Сеанс Twitch завершён. Войдите заново.');
            if (append(next)) return true;
        }
        return false;
    }
    if (!append(batch) && !advance()) page.metadata.notice = 'В этом разделе пока ничего нет.';
    if (cursor && !cursors[cursor]) page.paginator = function() {
        try {
            advance();
            return !!cursor && !cursors[cursor];
        } catch (e) {
            page.metadata.notice = e.message || String(e);
            return false;
        }
    };
}

function seconds(duration) {
    var total = 0;
    String(duration || '').replace(/(\d+)([hms])/g, function(_, n, unit) {
        total += Number(n) * (unit === 'h' ? 3600 : unit === 'm' ? 60 : 1);
    });
    return total;
}

function helixItem(kind, item) {
    var node = {id: item.id, title: item.title, language: item.language, viewCount: item.view_count};
    if (kind === 'clips') {
        node.slug = item.id;
        node.durationSeconds = item.duration;
        node.thumbnailURL = item.thumbnail_url;
        node.broadcaster = {displayName: item.broadcaster_name};
    } else if (kind === 'videos') {
        node.lengthSeconds = seconds(item.duration);
        node.previewThumbnailURL = item.thumbnail_url;
        node.owner = {displayName: item.user_name};
    } else {
        node.broadcaster = {login: item.user_login, displayName: item.user_name};
        node.createdAt = item.started_at;
        node.viewersCount = item.viewer_count;
        node.previewImageURL = art(item.thumbnail_url, 640, 360);
        if (item.game_name) node.game = {name: item.game_name, slug: item.game_id ? 'id-' + item.game_id : ''};
    }
    return node;
}

function topGames(cursor) {
    var batch = account.catalog('games/top', {}, cursor);
    if (!batch) return null;
    var games = batch.nodes.filter(function(game) { return game && /^\d+$/.test(game.id); });
    var stats = twitch.gameStats(games.map(function(game) { return game.id; }));
    batch.nodes = games.map(function(game) {
        var counts = stats['g' + game.id] || {};
        return {slug: 'id-' + game.id, displayName: game.name, boxArtURL: art(game.box_art_url, 288, 384),
            channelsCount: counts.channelsCount, viewersCount: counts.viewersCount};
    });
    return batch;
}

function helixListing(page, kind, scope, key) {
    if (!account.login()) return false;
    var load = topGames;
    if (kind !== 'games') {
        var filters = {};
        if (scope === 'category') filters.game_id = twitch.category(key).id;
        if (scope === 'channel') {
            filters[kind === 'clips' ? 'broadcaster_id' : 'user_id'] = twitch.channel(key).id;
        }
        if (kind === 'videos' && scope === 'category') filters.sort = 'views';
        load = function(cursor) {
            var batch = account.catalog(kind, filters, cursor);
            if (batch) batch.nodes = batch.nodes.map(function(item) { return helixItem(kind, item); });
            return batch;
        };
    }
    var batch = load();
    if (!batch) return false;
    attachCatalog(page, kind, batch, load);
    return true;
}

function listing(page, name, kind, scope, key) {
    directory(page, name, kind, kind === 'games' ? 'poster' : 'video');
    if (helixListing(page, kind, scope, key)) return;
    // The anonymous GraphQL path rejects cursors; streams are limited to 30 per request.
    var paged = kind !== 'streams' || scope === 'category';
    var result = twitch.list(kind, scope, key, paged ? 100 : 30);
    var items = result.nodes;
    var offset = 0;
    page.metadata.catalogTotal = items.length;
    if (!items.length) page.metadata.notice = 'В этом разделе пока ничего нет.';
    function appendBatch() {
        var end = Math.min(offset + 24, items.length);
        while (offset < end) listItem(page, kind, items[offset++]);
        if (offset < items.length) return true;
        if (result.hasMore) page.metadata.notice = 'Для следующих страниц войдите в Twitch.';
        return false;
    }
    if (appendBatch()) page.paginator = appendBatch;
}

function searchRows(page, result, section, append) {
    var edges = result && result[section] && result[section].edges || [];
    var count = 0;
    edges.forEach(function(edge) {
        var item = edge && edge.item;
        if (item && (item.login || item.slug)) {
            append(page, item);
            count++;
        }
    });
    return count;
}

function search(page, query, textOnly) {
    var heading = 'Поиск Twitch: ' + query;
    if (textOnly) {
        page.type = 'directory';
        page.metadata.title = heading;
    } else {
        directory(page, heading, 'search', 'cards');
    }
    var result = twitch.search(query);
    var count = searchRows(page, result, 'channels', channelItem) + searchRows(page, result, 'games', categoryItem);
    if (!count) {
        if (textOnly) label(page, 'Ничего не найдено.');
        else page.metadata.notice = 'Ничего не найдено.';
    }
}

function input() {
    var result = popup.textDialog('Канал, категория или ссылка Twitch', true, true);
    return result.rejected ? '' : String(result.input || '').trim();
}

function destination(query) {
    var match = /^https?:\/\/(?:www\.|m\.)?twitch\.tv\/videos\/([0-9]+)\/?(?:[?#].*)?$/i.exec(query);
    if (match) return url('play:vod', match[1]);
    match = new RegExp('^https?://(?:clips\\.twitch\\.tv/|(?:www\\.|m\\.)?twitch\\.tv/' + loginPattern +
                       '/clip/)(' + slugPattern + ')/?(?:[?#].*)?$', 'i').exec(query);
    if (match) return url('play:clip', match[1]);
    match = /^https?:\/\/(?:www\.|m\.)?twitch\.tv\/directory\/category\/([A-Za-z0-9_-]+)\/?(?:[?#].*)?$/i.exec(query);
    if (match) return url('category', match[1]);
    // Twitch reserves these names for its own pages, so no channel can have them.
    match = new RegExp('^https?://(?:www\\.|m\\.)?twitch\\.tv/(?!(?:directory|settings|search|videos|downloads|' +
                       'subscriptions|inventory|wallet|drops|turbo|friends|messages)(?:[/?#]|$))(' + loginPattern +
                       ')(?:/(?:videos|clips|about|schedule))?/?(?:[?#].*)?$', 'i').exec(query);
    if (match) return url('channel', match[1].toLowerCase());
    return url('search', query);
}

function streams(page) { listing(page, 'Прямые эфиры', 'streams'); }

route('start$', streams);
route('streams$', streams);
route('(videos|clips)$', function(page, kind) {
    directory(page, sections[kind], kind, 'video');
    // Twitch has no global clips/videos endpoint: collect popular media by category.
    var ids = twitch.popularGames();
    var offset = 0;
    function load() {
        var group = ids.slice(offset, offset + 8);
        offset += group.length;
        return {nodes: group.length ? twitch.popularMedia(kind, group) : [],
            next: offset < ids.length ? String(offset) : null};
    }
    attachCatalog(page, kind, load(), load);
});
route('categories$', function(page) { listing(page, 'Категории Twitch', 'games'); });

route('account$', function(page) {
    directory(page, 'Аккаунт Twitch', 'account', 'detail', icon);
    accountPage(page);
});
function followedChannels(cursor) {
    var batch = account.catalog('channels/followed', {user_id: account.userId()}, cursor);
    if (batch) batch.nodes = twitch.users(batch.nodes.map(function(follow) { return follow.broadcaster_login; }));
    return batch;
}

// Local favorites first, then the channels the account follows on Twitch (read-only: Twitch has no follow API).
route('favorites$', function(page) {
    directory(page, 'Избранные каналы', 'favorites', 'cards');
    var batch = account.userId() && followedChannels() || {nodes: []};
    batch.nodes = savedChannels().concat(batch.nodes);
    attachCatalog(page, 'channels', batch, followedChannels);
    if (account.login() && !account.userId()) page.metadata.notice = 'Войдите заново, чтобы показать подписки Twitch.';
    else if (!batch.nodes.length) page.metadata.notice = 'Добавьте канал в избранное на его странице.';
});

route('search:(.+)$', function(page, query) { search(page, decodeURIComponent(query)); });
route('channel:(' + loginPattern + ')$', function(page, login) {
    var user = twitch.channel(login);
    directory(page, user.displayName || login, 'streams', 'detail', user.profileImageURL);
    if (user.stream) streamItem(page, user.stream, user);
    else page.metadata.detail = 'Сейчас не в эфире';
    link(page, 'list:channel:videos', 'Записи', user.login);
    link(page, 'list:channel:clips', 'Клипы', user.login);
    function favoriteTitle() {
        return favoriteIndex(savedChannels(), user.login) < 0 ? 'Добавить в избранное' : 'Убрать из избранного';
    }
    var item = page.appendAction(favoriteTitle(), function() {
        toggleFavorite(user);
        item.root.metadata.title = favoriteTitle();
    });
});

route('category:(.+)$', function(page, encoded) {
    var slug = decodeURIComponent(encoded);
    var game = twitch.category(slug);
    directory(page, game.displayName || slug, 'games', 'detail', game.boxArtURL);
    link(page, 'list:category:streams', 'Трансляции', slug);
    link(page, 'list:category:videos', 'Записи', slug);
    link(page, 'list:category:clips', 'Клипы', slug);
});

var sections = {streams: 'Трансляции', videos: 'Записи', clips: 'Клипы'};
route('list:(channel|category):(streams|videos|clips):(.+)$', function(page, scope, kind, encoded) {
    var key = decodeURIComponent(encoded);
    if (scope === 'channel' && kind === 'streams') throw new Error('Откройте трансляцию на странице канала.');
    listing(page, sections[kind] + ' · ' + key, kind, scope, key);
});

function playback(page, kind, id) {
    var media = twitch.play(kind, id);
    var choices = kind === 'clip' ? media : live.variants(media.url, kind === 'live');
    var selected;
    function selectQuality(index) {
        page.metadata.qualityOpen = false;
        if (selected === index) return;
        var item = choices.items[index];
        if (selected !== undefined && kind !== 'live') page.root.how = 'resume';
        selected = index;
        page.metadata.quality = item.label;
        page.metadata.qualityIndex = index;
        page.source = 'videoparams:' + JSON.stringify({title: media.title, canonicalUrl: url('play:' + kind, id),
            sources: [{url: item.url}], live: kind === 'live', no_subtitle_scan: true});
    }
    function rememberQuality(index) {
        quality.remember(choices.items[index]);
        selectQuality(index);
    }
    page.type = 'raw';
    page.metadata.glwview = Plugin.path + 'views/player.view';
    page.metadata.title = media.title;
    choices.items.forEach(function(item, index) {
        var action = page.appendAction(item.label, function() { rememberQuality(index); });
        action.root.metadata.index = index;
        page.onEvent('TwitchQuality' + index, function() { rememberQuality(index); });
    });
    selectQuality(quality.initial(choices));
}

route('play:live:(' + loginPattern + ')$', function(page, id) { playback(page, 'live', id); });
route('play:vod:([0-9]+)$', function(page, id) { playback(page, 'vod', id); });
route('play:clip:(' + slugPattern + ')$', function(page, id) { playback(page, 'clip', id); });

new pages.Searcher(title, icon, function(page, query) {
    try {
        search(page, query, true);
    } catch (e) {
        label(page, e.message || String(e));
    }
    page.loading = false;
});
service.create(title, url('start'), 'video', true, icon);
