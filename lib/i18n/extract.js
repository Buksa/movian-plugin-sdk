#!/usr/bin/env node
// Lists a Movian plugin's user-visible strings for a human to review before they
// move to t('English') with lang/<code>.lang files, and to L(key) text ids in views
// (the pattern in docs/i18n.md of STT for Movian, formerly SmartTwitchTV,
// https://github.com/Buksa/movian-plugin-stt/blob/master/docs/i18n.md). Plugin JS is parsed with Acorn and never run;
// views go through the core's own GLW lexer (movian-analyze --tokens).
// Usage: extract.js extract <plugin-dir> [--json]
'use strict';
var fs = require('fs');
var path = require('path');
var childProcess = require('child_process');
var acorn = require('acorn');

// ---------------------------------------------------------------- text tests

function hasLetter(s) {
    return /\p{L}/u.test(s.replace(/%[-+ #0]*\d*(?:\.\d+)?[a-zA-Z]/g, '')); // strftime/printf codes are not words
}

// Could a person read this? Ids, keys, routes, paths and URLs cannot.
function textLike(s) {
    if (!hasLetter(s) || /:\/\/|^\.{0,2}\//.test(s)) return false;
    if (/\s/.test(s)) return true;
    if (/^[\w.-]+:/.test(s)) return false;                    // route prefix 'plugin:start'
    if (/^[\w./-]+\.[a-z0-9]{2,4}$/i.test(s)) return false;   // logo.png
    if (/^[a-z0-9_.:/$-]+$/.test(s)) return false;            // lowercase id/type/key/route part
    if (/^[a-z]+[A-Z]\w*$/.test(s)) return false;             // camelCase key or event
    return true;
}

// Text with no known sink is listed only when it is clearly a sentence.
function sentence(s) {
    return /\p{L}{2,}\s+\p{L}{2,}/u.test(s) && !/[{}<>=;$|\\/]|\b[a-z]+[A-Z]/.test(s);  // no code, no camelCase fields
}

function placeholders(s) {
    return s.match(/%(?:\d+\$)?[sdif]|\{\d+\}/g) || [];
}

var notLatin = /(?=\p{L})\P{Script=Latin}/u;

// ---------------------------------------------------------------- JS

// Movian plugin API arguments shown to the user (res/ecmascript/modules/movian/
// page.js, settings.js, service.js; native/popup).
var API_ARGS = {
    appendAction: [0], addOptURL: [0], addOptAction: [0], addOptSeparator: [0], error: [0],
    notify: [0], textDialog: [0], message: [0], Searcher: [0],
    createDivider: [0], createBool: [1], createString: [1], createInt: [1], createMultiOpt: [1],
    createAction: [1], createInfo: [2], globalSettings: [1, 3]
};
var TEXT_KEYS = {title: 1, description: 1, label: 1};  // item metadata, option objects
// A string anywhere inside these calls is code, not UI. trace() is Movian's log.
var CODE_CALLS = {require: 1, RegExp: 1, print: 1, trace: 1, log: 1, debug: 1, parseInt: 1, parseFloat: 1,
    encodeURIComponent: 1, decodeURIComponent: 1, escape: 1, unescape: 1};
var CODE_METHODS = {request: 1, test: 1, match: 1, replace: 1, split: 1, indexOf: 1, lastIndexOf: 1,
    search: 1, exec: 1, startsWith: 1, endsWith: 1, includes: 1, onEvent: 1, subscribe: 1,
    addEventListener: 1, Route: 1, getElementById: 1, getElementsByTagName: 1,
    getElementsByClassName: 1, querySelector: 1, querySelectorAll: 1, attr: 1, setHeader: 1,
    getHeader: 1, getItem: 1, setItem: 1, removeItem: 1, join: 1, charAt: 1, substr: 1};
var CODE_OBJECTS = {console: 1, JSON: 1, Math: 1};
var TRANSLATORS = {t: 1, tr: 1, _: 1, getString: 1};  // existing t('…') calls
var COMPARE = {'==': 1, '===': 1, '!=': 1, '!==': 1, 'in': 1, 'instanceof': 1};

function isString(n) { return n.type === 'Literal' && typeof n.value === 'string'; }
function isFunction(n) { return /Function/.test(n.type); }

function walk(node, parent, visit) {
    node.parent = parent;
    visit(node);
    for (var key in node) {
        if (key === 'parent' || key === 'loc') continue;
        var value = node[key];
        if (Array.isArray(value)) {
            value.forEach(function(child) { if (child && typeof child.type === 'string') walk(child, node, visit); });
        } else if (value && typeof value.type === 'string') {
            walk(value, node, visit);
        }
    }
}

function calleeName(call) {
    var c = call.callee;
    if (c.type === 'Identifier') return c.name;
    if (c.type === 'MemberExpression' && !c.computed) return c.property.name;
    return null;
}

function calleeObject(call) {
    var c = call.callee;
    if (c.type !== 'MemberExpression') return null;
    if (c.object.type === 'Identifier') return c.object.name;
    if (c.object.type === 'MemberExpression' && !c.object.computed) return c.object.property.name;
    return null;
}

function functionName(fn) {
    if (fn.id) return fn.id.name;
    var p = fn.parent;
    if (p.type === 'VariableDeclarator' && p.id.type === 'Identifier') return p.id.name;
    if (p.type === 'AssignmentExpression' && p.left.type === 'Identifier') return p.left.name;
    return null;
}

// Walk up through parts that pass a value on unchanged; `chain` is the outermost
// string `+` on the way, the unit a translator sees as one sentence.
function climb(node) {
    var chain = null;
    for (;;) {
        var p = node.parent;
        if (p.type === 'ConditionalExpression' && p.test !== node) node = p;
        else if (p.type === 'LogicalExpression') node = p;
        else if (p.type === 'BinaryExpression' && p.operator === '+') { chain = node = p; }
        else if (p.type === 'SequenceExpression' && p.expressions[p.expressions.length - 1] === node) node = p;
        else return {use: node, chain: chain};
    }
}

function insideCode(node) {
    for (var child = node, p = node.parent; p && !isFunction(p); child = p, p = p.parent) {
        if ((p.type === 'CallExpression' || p.type === 'NewExpression') && p.arguments.indexOf(child) >= 0) {
            var name = calleeName(p);
            if (p.callee.type === 'Identifier' ? CODE_CALLS[name] : CODE_METHODS[name] || CODE_OBJECTS[calleeObject(p)]) return true;
        }
    }
    return false;
}

// Another argument of a Movian API call: an id, url, type or setting default.
function apiArgument(use) {
    var p = use.parent;
    return (p.type === 'CallExpression' || p.type === 'NewExpression') && p.callee.type === 'MemberExpression' &&
        p.arguments.indexOf(use) >= 0 && !!(API_ARGS[calleeName(p)] || /^append(Passive)?Item$/.test(calleeName(p)));
}

function atModuleLoad(node) {
    for (var p = node.parent; p; p = p.parent) {
        // An IIFE wrapper runs at load too.
        if (isFunction(p) && !(p.parent.type === 'CallExpression' && p.parent.callee === p)) return false;
    }
    return true;
}

function JsFile(file, source) {
    this.file = file;
    this.source = source;
    this.ast = acorn.parse(source, {ecmaVersion: 'latest', sourceType: 'script', locations: true,
        allowReturnOutsideFunction: true, allowHashBang: true});
    var nodes = this.nodes = [];
    walk(this.ast, null, function(n) { nodes.push(n); });
    var functions = this.functions = Object.create(null);
    nodes.forEach(function(n) {
        if (isFunction(n)) {
            var name = functionName(n);
            if (name && !functions[name]) functions[name] = n;
        }
    });
    // shortcut: names are per file, not per scope; two `name` variables in one file
    // count as one. Upgrade to scope analysis if reviews show false hits from it.
    this.names = Object.create(null);    // variable/param -> where its value is shown
    this.tables = Object.create(null);   // object read as table[key] where text is shown
    this.returns = Object.create(null);  // local function whose result is shown
    this.flow();
}

// Where does a value at `use` end up on screen? A label, or null.
JsFile.prototype.sinkOf = function(use) {
    var p = use.parent;
    if (p.type === 'CallExpression' || p.type === 'NewExpression') {
        var i = p.arguments.indexOf(use);
        if (i < 0) return null;
        var name = calleeName(p);
        if (!name) return null;
        if (p.callee.type === 'Identifier' && /Error$/.test(name)) return 'new ' + name + '()';
        if (TRANSLATORS[name]) return name + '()';
        var method = p.callee.type === 'MemberExpression';  // the API is methods; a local error() is not page.error()
        if (method && API_ARGS[name] && API_ARGS[name].indexOf(i) >= 0) return name + '()';
        if (method && name === 'create' && /service/i.test(calleeObject(p) || '') && i === 0) return 'service.create()';
        var fn = p.callee.type === 'Identifier' && this.functions[name];
        var param = fn && fn.params[i];
        if (param && param.type === 'Identifier' && this.names[param.name]) {
            return name + '(#' + i + ') → ' + this.names[param.name];
        }
        return null;
    }
    if (p.type === 'Property' && p.value === use && !p.computed) {
        var key = p.key.name || p.key.value;
        if (TEXT_KEYS[key]) return key + ':';
        var obj = p.parent.parent;
        var table = obj.type === 'VariableDeclarator' ? obj.id.name :
            obj.type === 'AssignmentExpression' && obj.left.type === 'Identifier' ? obj.left.name : null;
        return table && this.tables[table] ? table + '[…] → ' + this.tables[table] : null;
    }
    if (p.type === 'ArrayExpression' && p.elements[1] === use && p.parent.type === 'ArrayExpression' &&
        p.parent.parent.type === 'CallExpression' && calleeName(p.parent.parent) === 'createMultiOpt' &&
        p.parent.parent.arguments[2] === p.parent) {
        return 'createMultiOpt() option';
    }
    if (p.type === 'AssignmentExpression' && p.right === use) {
        var left = p.left;
        if (left.type === 'Identifier') return this.names[left.name] ? left.name + ' → ' + this.names[left.name] : null;
        if (left.type === 'MemberExpression' && !left.computed) {
            var prop = left.property.name;
            var o = left.object;
            if (o.type === 'MemberExpression' && !o.computed && o.property.name === 'metadata') return 'metadata.' + prop;
            if (TEXT_KEYS[prop]) return '.' + prop;
        }
        return null;
    }
    if (p.type === 'VariableDeclarator' && p.init === use && p.id.type === 'Identifier') {
        return this.names[p.id.name] ? p.id.name + ' → ' + this.names[p.id.name] : null;
    }
    if (p.type === 'ReturnStatement') {
        for (var f = p.parent; f && !isFunction(f); f = f.parent);
        var fname = f && functionName(f);
        return fname && this.returns[fname] ? fname + '() → ' + this.returns[fname] : null;
    }
    return null;
};

// Which local names, tables and functions carry text into a sink? Iterate until stable.
JsFile.prototype.flow = function() {
    for (var changed = true, rounds = 0; changed && rounds < 20; rounds++) {
        changed = false;
        for (var k = 0; k < this.nodes.length; k++) {
            var n = this.nodes[k];
            var target, into;
            if (n.type === 'Identifier' && n.parent && !(n.parent.type === 'MemberExpression' && n.parent.property === n && !n.parent.computed) &&
                !(n.parent.type === 'Property' && n.parent.key === n)) {
                target = n.name; into = this.names;
            } else if (n.type === 'MemberExpression' && n.computed && n.object.type === 'Identifier') {
                target = n.object.name; into = this.tables;
            } else if (n.type === 'CallExpression' && n.callee.type === 'Identifier' && this.functions[n.callee.name]) {
                target = n.callee.name; into = this.returns;
            } else continue;
            if (into[target]) continue;
            var sink = this.sinkOf(climb(n).use);
            if (sink && !/^(t|tr|_|getString)\(\)$/.test(sink)) { into[target] = sink; changed = true; }
        }
    }
};

// `a + b + 'c'` → 'a%s…' with the non-literal parts as arguments.
JsFile.prototype.template = function(node, out) {
    if (node.type === 'BinaryExpression' && node.operator === '+') {
        this.template(node.left, out);
        this.template(node.right, out);
    } else if (isString(node)) {
        out.text += node.value;
    } else {
        out.text += '%s';
        out.args.push(this.source.slice(node.start, node.end));
    }
    return out;
};

JsFile.prototype.entries = function() {
    var self = this;
    var out = [];
    var seen = Object.create(null);
    this.nodes.forEach(function(n) {
        if (!isString(n)) return;
        var p = n.parent;
        if (p.type === 'Property' && p.key === n) return;
        if (p.type === 'MemberExpression') return;                    // obj['key'], 'x'.length
        if (p.type === 'ImportDeclaration' || p.type === 'ExpressionStatement' && p.directive) return;
        var up = climb(n);
        var use = up.use;
        if (use.parent.type === 'BinaryExpression' && COMPARE[use.parent.operator]) return;
        if (use.parent.type === 'SwitchCase' && use.parent.test === use) return;
        if (insideCode(n)) return;
        var node = up.chain || n;
        var flags = [];
        var text = n.value, args = [];
        if (up.chain) {
            var t = self.template(up.chain, {text: '', args: []});
            if (t.args.length) { flags.push('concatenation'); args = t.args; }
            text = t.text;
        }
        var literalText = up.chain ? text.replace(/%s/g, '') : text;
        if (!textLike(literalText)) return;
        if (seen[node.start]) return;
        seen[node.start] = true;
        var sink = self.sinkOf(use);
        if (!sink) {
            if (apiArgument(use) || !sentence(literalText)) return;
            flags.push('no-sink');
        } else if (/^(t|tr|_|getString)\(\)/.test(sink)) {
            flags.push('already-localized');
        } else if (/Error\(\)/.test(sink)) {
            flags.push('error-message');
        }
        if (atModuleLoad(n) && flags.indexOf('already-localized') < 0) flags.push('module-load');
        out.push({file: self.file, line: node.loc.start.line, col: node.loc.start.column + 1,
            span: [node.start, node.end], text: text, sink: sink || '',
            placeholders: args.length ? args : placeholders(text), flags: flags});
    });
    return out;
};

// ---------------------------------------------------------------- GLW views

var TEXT_ATTRS = {caption: 1, description: 1};          // glw_view_attrib.c
var PASS_THROUGH = {select: 1, fmt: 1, join: 1, translate: 1};  // builtins whose string args can be shown
var OPEN = {LEFT_PARENTHESIS: 1, LEFT_BRACKET: 1, BLOCK_OPEN: 1};
var CLOSE = {RIGHT_PARENTHESIS: 1, RIGHT_BRACKET: 1, BLOCK_CLOSE: 1};

function analyzer() {
    var core;
    try {
        core = childProcess.execFileSync('mdev', ['core'], {encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit']}).trim();
    } catch (e) {
        throw new Error('views need the Movian core: `mdev core` failed (see mdev doctor)');
    }
    var bin = path.join(core, 'build.debug', 'movian-analyze');
    if (!fs.existsSync(bin)) {
        throw new Error(bin + ' is missing; build it: (cd ' + core + ' && make BUILD=debug -j$(nproc) movian-analyze)');
    }
    var metadata = JSON.parse(fs.readFileSync(path.join(core, 'generated', 'movian-metadata.json'), 'utf8'));
    var builtins = Object.create(null);
    metadata.glw.functions.forEach(function(f) { builtins[f.name || f] = true; });
    return {bin: bin, builtins: builtins};
}

function tokens(tool, dir, rel) {
    // --max-depth 0: each view is read on its own; includes are listed separately.
    var run = childProcess.spawnSync(tool.bin, ['--tokens', '--max-depth', '0', '--root', dir, rel],
        {cwd: dir, encoding: 'utf8', maxBuffer: 64 << 20});
    var json;
    try { json = JSON.parse(run.stdout); } catch (e) { json = {error: (run.stderr || 'no output').trim()}; }
    if (!json.tokens) throw new Error(rel + ':' + (json.line || '?') + ': ' + json.error);
    return json.tokens.filter(function(t) { return t.file === rel; });
}

// #define NAME(A, B) { body }
function macros(toks, into) {
    for (var i = 0; i + 3 < toks.length; i++) {
        if (toks[i].type !== 'HASH' || toks[i + 1].value !== 'define' || toks[i + 2].type !== 'IDENTIFIER') continue;
        var name = toks[i + 2].value, params = [], j = i + 3;
        if (toks[j].type === 'LEFT_PARENTHESIS') {
            for (j++; j < toks.length && toks[j].type !== 'RIGHT_PARENTHESIS'; j++) {
                if (toks[j].type === 'IDENTIFIER') params.push(toks[j].value);
            }
            j++;
        }
        var start = j, depth = 0;
        for (; j < toks.length; j++) {
            if (OPEN[toks[j].type]) depth++;
            else if (CLOSE[toks[j].type] && --depth <= 0) break;
        }
        var body = toks.slice(start, j + 1);
        into[name] = {params: params, body: body,
            localized: body.some(function(t) { return t.value === 'i18n'; })};
    }
}

// From token i, find the nearest enclosing attribute or call.
function enclosing(toks, i) {
    for (var depth = 0, j = i - 1; j >= 0; j--) {
        var type = toks[j].type;
        if (CLOSE[type]) depth++;
        else if (OPEN[type]) {
            if (depth > 0) { depth--; continue; }
            if (type !== 'LEFT_PARENTHESIS' || !toks[j - 1] || toks[j - 1].type !== 'IDENTIFIER') return {};
            for (var arg = 0, d = 0, k = j + 1; k < i; k++) {
                if (OPEN[toks[k].type]) d++;
                else if (CLOSE[toks[k].type]) d--;
                else if (d === 0 && toks[k].type === 'SEPARATOR') arg++;
            }
            return {call: toks[j - 1].value, arg: arg, at: j - 1};
        } else if (depth === 0) {
            if (type === 'COLON' && toks[j - 1] && toks[j - 1].type === 'IDENTIFIER') return {attr: toks[j - 1].value};
            if (type === 'END_OF_EXPR' || /ASSIGN/.test(type)) return {};
        }
    }
    return {};
}

var RANK = {text: 3, flag: 2, none: 1, skip: 0};

// What a string (or macro parameter) at toks[i] becomes: {kind, sink, flag}.
function glwUse(toks, i, ctx, depth) {
    var prev = toks[i - 1], next = toks[i + 1];
    if (prev && /^N?EQ$/.test(prev.type) || next && /^N?EQ$/.test(next.type)) return {kind: 'skip'};
    if (prev && (prev.value === 'include' || prev.value === 'import')) return {kind: 'skip'};
    var via = '';
    for (var pos = i;;) {
        var e = enclosing(toks, pos);
        if (e.attr) return TEXT_ATTRS[e.attr] ? {kind: 'text', sink: via + e.attr} : {kind: 'skip'};
        if (!e.call) return {kind: 'none'};
        if (e.call === '_' || e.call === '_pl') return {kind: 'flag', flag: 'already-localized', sink: via + e.call + '()'};
        var m = ctx.macros[e.call];
        if (m) {
            if (m.localized) return {kind: 'flag', flag: 'already-localized', sink: via + e.call + '()'};
            var param = m.params[e.arg];
            if (!param || depth > 8) return {kind: 'skip'};
            var best = {kind: 'skip'};
            m.body.forEach(function(t, k) {
                if (t.type !== 'IDENTIFIER' || t.value !== param) return;
                var r = glwUse(m.body, k, ctx, depth + 1);
                if (RANK[r.kind] > RANK[best.kind]) best = r;
            });
            if (best.sink) best = {kind: best.kind, flag: best.flag, sink: via + e.call + '(#' + e.arg + ') → ' + best.sink};
            return best;
        }
        if (!ctx.builtins[e.call]) return {kind: 'flag', flag: 'unknown-macro', sink: via + e.call + '(#' + e.arg + ')'};
        if (!PASS_THROUGH[e.call]) return {kind: 'skip'};
        via += e.call + '() → ';
        pos = e.at;
    }
}

function viewEntries(rel, source, toks, ctx) {
    var lines = source.split('\n');
    var starts = [0];
    lines.forEach(function(l, k) { starts.push(starts[k] + l.length + 1); });
    var cursor = {};
    var out = [];
    toks.forEach(function(t, i) {
        if (t.type !== 'RSTRING' || !textLike(t.value)) return;
        var use = glwUse(toks, i, ctx, 0);
        if (use.kind === 'skip' || use.kind === 'none' && !sentence(t.value)) return;
        // The analyzer gives lines, not columns: find the literal on its line.
        // shortcut: misses literals with escapes or spanning lines (col stays null).
        var line = lines[t.line - 1] || '';
        var from = cursor[t.line] || 0, col = -1, quote = '"';
        ['"', "'"].forEach(function(q) {
            var at = line.indexOf(q + t.value + q, from);
            if (at >= 0 && (col < 0 || at < col)) { col = at; quote = q; }
        });
        if (col >= 0) cursor[t.line] = col + t.value.length + 2;
        var flags = use.kind === 'none' ? ['no-sink'] : use.flag ? [use.flag] : [];
        out.push({file: rel, line: t.line, col: col < 0 ? null : col + 1,
            span: col < 0 ? null : [starts[t.line - 1] + col, starts[t.line - 1] + col + t.value.length + 2],
            text: t.value, sink: (use.sink || '') + (quote === "'" ? ' (rich text)' : ''),
            placeholders: placeholders(t.value), flags: flags});
    });
    return out;
}

// ---------------------------------------------------------------- plugin

function files(dir, ext) {
    var out = [];
    (function scan(rel) {
        fs.readdirSync(path.join(dir, rel), {withFileTypes: true}).forEach(function(d) {
            var r = path.join(rel, d.name);
            if (d.isDirectory()) {
                if (!/^(\.|node_modules$|tests?$)/.test(d.name)) scan(r);
            } else if (d.name.endsWith(ext)) out.push(r);
        });
    })('');
    return out.sort();
}

function extract(dir) {
    var report = {plugin: path.resolve(dir), notes: [], entries: []};
    var localized = [];
    files(dir, '.js').forEach(function(rel) {
        var source = fs.readFileSync(path.join(dir, rel), 'utf8');
        var js;
        try { js = new JsFile(rel, source); } catch (e) {
            report.notes.push(rel + ': not parsed (' + e.message + '); its strings are not listed');
            return;
        }
        report.entries = report.entries.concat(js.entries());
        js.nodes.forEach(function(n) {
            if (n.type === 'MemberExpression' && !n.computed && n.property.name === 'getString' &&
                n.object.type === 'Identifier' && n.object.name === 'Core') {
                localized.push(rel + ':' + n.loc.start.line + ' Core.getString (Movian-Go catalog)');
            } else if (n.type === 'MemberExpression' && !n.computed && n.property.name === 'iso639_1') {
                localized.push(rel + ':' + n.loc.start.line + ' reads i18n.iso639_1');
            } else if (n.type === 'CallExpression' && calleeName(n) === 'createMultiOpt' && n.arguments[0] &&
                isString(n.arguments[0]) && /^(ui_?)?lang(uage)?$/i.test(n.arguments[0].value)) {  // not 'subtitle_langs'
                localized.push(rel + ':' + n.loc.start.line + ' own language setting "' + n.arguments[0].value + '"');
            }
        });
    });
    if (files(dir, '.lang').length) localized.push('ships .lang files');
    var views = files(dir, '.view');
    if (views.length) {
        var tool = analyzer();
        var ctx = {builtins: tool.builtins, macros: Object.create(null)};
        var all = [];
        views.forEach(function(rel) {
            try {
                var toks = tokens(tool, dir, rel);
                macros(toks, ctx.macros);
                all.push([rel, toks]);
            } catch (e) {
                report.notes.push('view not read: ' + e.message);
            }
        });
        // shortcut: macros from every view are visible to every view, not only to
        // the views that #include them. Upgrade if two views define one name differently.
        all.forEach(function(v) {
            var source = fs.readFileSync(path.join(dir, v[0]), 'utf8');
            report.entries = report.entries.concat(viewEntries(v[0], source, v[1], ctx));
        });
    }
    if (localized.length) {
        report.notes.push('already localized, do not rewrite: ' + localized.join('; '));
        report.entries.forEach(function(e) {
            if (e.flags.indexOf('already-localized') < 0) e.flags.unshift('already-localized');
        });
    }
    var foreign = report.entries.filter(function(e) { return notLatin.test(e.text); }).length;
    if (foreign) report.notes.push(foreign + ' of ' + report.entries.length + ' strings are not in English: the English key must be written by hand');
    report.counts = {};
    report.entries.forEach(function(e) {
        e.status = e.flags.length ? 'flag: ' + e.flags.join(', ') : 'candidate';
        (e.flags.length ? e.flags : ['candidate']).forEach(function(key) {
            report.counts[key] = (report.counts[key] || 0) + 1;
        });
    });
    return report;
}

function readable(report) {
    var lines = [report.plugin];
    report.notes.forEach(function(n) { lines.push('note: ' + n); });
    lines.push('counts (an entry counts once per flag): ' + JSON.stringify(report.counts), '');
    report.entries.forEach(function(e) {
        lines.push(e.file + ':' + e.line + ':' + (e.col || '?') + '  ' + e.status + '  ' + (e.sink || '-') +
            '  ' + JSON.stringify(e.text) + (e.placeholders.length ? '  [' + e.placeholders.join(', ') + ']' : ''));
    });
    return lines.join('\n') + '\n';
}

if (require.main === module) {
    var args = process.argv.slice(2);
    var json = args.indexOf('--json') >= 0;
    args = args.filter(function(a) { return a !== '--json'; });
    if (args[0] !== 'extract' || args.length !== 2) {
        process.stderr.write('usage: extract.js extract <plugin-dir> [--json]\n');
        process.exit(2);
    }
    try {
        var report = extract(args[1]);
        process.stdout.write(json ? JSON.stringify(report, null, 1) + '\n' : readable(report));
    } catch (e) {
        process.stderr.write('extract: ' + e.message + '\n');
        process.exit(1);
    }
}

module.exports = {extract: extract, textLike: textLike};
