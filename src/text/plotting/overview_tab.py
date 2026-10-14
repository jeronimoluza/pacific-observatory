"""The concepts dashboard's Overview tab: what is happening now, per unit.

Read ``outputs/text/<region>/overview.json`` (written by
``src/text/analysis/explorations/overview.py``). A dropdown picks the region,
a subregion or a country. Per unit: KPIs, filter toggles, one full-width card
per topic (bursting, elevated, cooling, or with a 7-day state) and, for the
region and subregions, a heat grid of countries x top topics. The Uncertainty
Topics tab stays the place to explore topic combinations.

A card: the weekly Baker index as x usual (index / its mean over the
comparison period; the "Compare with" switch picks 2024, the past year, 26 or
8 weeks) for the last 52 weeks, burst weeks marked; the last 7 days as daily
bars against the expected daily count; two badge slots:

- Week (the last calendar week, Mon-Sun): Bursting 1st wk / Nth wk / rising
  N wks / past peak, Cooling (stopped bursting k weeks ago), Elevated N wks
  (4-week mean 1.5x its 2024 level for N weeks; long crises stop bursting).
- Last 7 days (the 7 UTC days ending on the newest day with articles in the
  region, to become the current time once collection runs continuously):
  Pressing (>= 2 of the last 3 days, >= 1.5x expected, >= 5 articles), Came
  back (none in the 14 days before, >= 10 in 2024), Gone quiet (important in
  the last 4 weeks, none in 7 days), else on or below pace. Expected = usual
  weekly count x the unit's articles in the 7 days / its usual weekly articles.

``THEME_HEAD`` is the World Bank careers site look (worldbank.org/ext/en/careers):
Open Sans and its colours, as CSS variables the dashboard's pages already use.
"""

from __future__ import annotations

import json

THEME_HEAD = """<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap">
<style>
:root {
    --bg: #f5f7f9; --panel: #ffffff; --text: #012740; --muted: #4b5e71;
    --accent: #004370; --accent2: #169af3; --border: #d4dee8; --soft: #e7edf3;
    --red: #da1e28; --green: #388004; --yellow: #e19d00;
}
body { font-family: "Open Sans", Roboto, -apple-system, "Segoe UI", sans-serif; }
h1, h2, h3, .title { font-weight: 700; }
</style>
"""

SHARED_CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); padding: 14px; font-size: 13px; }
button, select { font-family: inherit; }
.top { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 12px; }
.top h1 { font-size: 1.4em; }
.top .sub { color: var(--muted); margin-top: 2px; }
.controls { margin-left: auto; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: 4px; overflow: hidden; background: #fff; }
.seg span { padding: 5px 10px; color: var(--muted); font-size: 12px; }
.seg button { border: 0; border-left: 1px solid var(--border); background: #fff; color: var(--text); padding: 5px 10px; cursor: pointer; font-size: 12px; }
.seg button.on { background: var(--accent); color: #fff; }
select { padding: 6px 8px; border: 1px solid var(--border); border-radius: 4px; background: #fff; font-size: 13px; color: var(--text); white-space: pre; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.x { font-weight: 700; font-variant-numeric: tabular-nums; }
.n { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.badge { display: inline-block; font-size: 10.5px; font-weight: 600; border-radius: 4px; padding: 1px 6px; white-space: nowrap; }
.b-burst { border: 1px solid var(--red); color: var(--red); background: #fff; }
.b-cool { border: 1px solid var(--border); color: var(--muted); background: #fff; }
.b-elev { border: 1px solid #8a5f00; color: #8a5f00; background: #fff; }
.b-press { background: var(--red); color: #fff; }
.b-back { background: var(--green); color: #fff; }
.b-quiet { background: var(--muted); color: #fff; }
.pace { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.more { border: 0; background: none; color: var(--accent2); cursor: pointer; font-size: 12px; padding: 6px 0 0; font-weight: 600; }
.empty { color: var(--muted); padding: 12px 0; }
"""

SHARED_JS = r"""
const O = __OVERVIEW_JSON__;
const NAMES = __NAMES_JSON__;
const PERIODS = [['2024', '2024'], ['52', 'Past year'], ['26', '26 wk'], ['8', '8 wk']];
let per = 2;
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const name = u => NAMES[u] || u.replace(/_/g, ' ').replace(/\b./g, x => x.toUpperCase());
const parts = g => { const l = O.labels[g] || g; const i = l.indexOf(' · '); return i < 0 ? ['', l] : [l.slice(0, i), l.slice(i + 3)]; };
const fx = v => v === null || !isFinite(v) ? '–' : (v >= 10 ? Math.round(v) : v.toFixed(1)) + '×';
// No ratio: either no source with 2024 data covers it (u, ranked last) or it was absent in the period (all extra).
const score = r => r.u ? 0 : r.r[per] === null || r.r[per] <= 0 ? r.n : r.n - r.n / r.r[per];
const arts = n => `${n.toLocaleString('en')} article${n === 1 ? '' : 's'}`;
const ord = k => k + (k % 100 >= 11 && k % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][k % 10] || 'th');
const DAY = 864e5;
const fmtDay = (d, o = {}) => new Date(typeof d === 'string' ? d + 'T00:00:00Z' : d).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC', ...o});
const W0 = Date.parse(O.series_start + 'T00:00:00Z');
const weekEnd = k => W0 + k * 7 * DAY;
const weekLabel = () => { const e = Date.parse(O.week + 'T00:00:00Z'); return `Week of ${fmtDay(e - 6 * DAY)}–${fmtDay(e)}`; };
// The week slot: the calendar week's burst status, and elevated if so.
function weekBadges(r) {
    if (!r) return [];
    const out = [];
    if (r.b) {
        const [k, v] = r.b;
        const t = k === 'new' ? 'Bursting · 1st wk' : k === 'wk' ? `Bursting · ${ord(v)} wk` : k === 'rise' ? `Bursting · rising ${v} wks`
            : k === 'peak' ? 'Bursting · past peak' : `Cooling · ${v} wk ago`;
        const tip = k === 'peak' ? `peaked ${v} week${v > 1 ? 's' : ''} ago` : k === 'fade' ? `stopped bursting ${v} week${v > 1 ? 's' : ''} ago` : 'weekly count well above its trailing 26-week share';
        out.push(`<span class="badge b-${k === 'fade' ? 'cool' : 'burst'}" title="${tip}">${t}</span>`);
    }
    if (r.p) out.push(`<span class="badge b-elev" title="4-week mean above 1.5× its 2024 level for ${r.p} weeks in a row">Elevated ${r.p} wks</span>`);
    return out;
}
// Heartbeat: the 7 UTC days ending on the newest day with articles in the region
// (later: the current time), from the unit's 21 published days.
const B0 = Date.parse(O.beat_start + 'T00:00:00Z');
const BEAT_STATES = {press: 'Pressing', back: 'Came back', quiet: 'Gone quiet'};
const LATEST = (O.units.region ? O.units.region.beat.a : []).reduce((m, x, i) => x > 0 ? i : m, -1);
const todayIdx = () => LATEST >= 0 ? LATEST : Math.floor((Date.now() - B0) / DAY);
const dayOf = i => new Date(B0 + i * DAY);
function beat(u, g) {
    const b = O.units[u] && O.units[u].beat, row = b && b.g[g];
    if (!row) return null;
    // Days after the published ones have no articles yet (0); before them, unknown.
    const at = (v, i) => i < 0 ? null : i >= v.length ? 0 : v[i];
    const t = todayIdx(), idx = [0, 1, 2, 3, 4, 5, 6].map(k => t - 6 + k);
    const win = idx.map(i => at(row.d, i));
    const n7 = win.reduce((s, x) => s + (x || 0), 0);
    const a7 = idx.reduce((s, i) => s + (at(b.a, i) || 0), 0);
    let prior = 0;
    for (let i = t - 20; i < t - 6; i++) prior += at(row.d, i) || 0;
    const exp = b.ua[per] > 0 ? row.u[per] * a7 / b.ua[per] : 0;
    const recent = win.slice(4).filter(x => x > 0).length;
    const state = recent >= 2 && n7 >= 5 && n7 >= 1.5 * exp ? 'press'
        : row.h && prior === 0 && n7 > 0 ? 'back'
        : row.i && n7 === 0 ? 'quiet'
        : n7 >= exp ? 'on' : 'below';
    return {g, idx, win, n7, a7, exp, state, i: row.i, u: row.u[per]};
}
const stateBadge = bt => !bt ? '' : BEAT_STATES[bt.state] ? `<span class="badge b-${bt.state}">${BEAT_STATES[bt.state]}</span>`
    : `<span class="pace">${bt.state === 'on' ? 'On pace' : 'Below pace'}</span>`;
const lastDay = () => fmtDay(dayOf(todayIdx()));
const asofText = () => {
    const d = new Date(O.asof), f = (o) => d.toLocaleString('en-GB', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', ...o});
    return `Built ${f({})} your time (${f({timeZone: 'UTC'})} UTC)`;
};
"""

OVERVIEW_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>__SHARED_CSS__
.kpis { display: flex; gap: 28px; flex-wrap: wrap; margin-bottom: 14px; }
.kpi .v { font-size: 1.7em; font-weight: 700; color: var(--accent); line-height: 1.1; }
.kpi .v small { font-size: .5em; color: var(--muted); font-weight: 400; }
.kpi .t { color: var(--muted); font-size: 12px; }
.kpi .d { font-size: 12px; font-weight: 600; }
.up { color: var(--green); } .down { color: var(--red); }
.filters { display: flex; gap: 18px; flex-wrap: wrap; align-items: center; padding: 10px 0; border-top: 1px solid var(--soft); border-bottom: 1px solid var(--soft); margin-bottom: 8px; }
.fg { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.fg > span { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; margin-right: 2px; }
.tog { border: 1px solid var(--border); background: #fff; color: var(--text); border-radius: 14px; padding: 3px 10px; cursor: pointer; font-size: 12px; }
.tog b { font-variant-numeric: tabular-nums; margin-left: 4px; color: var(--muted); }
.tog.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.tog.on b { color: #fff; }
.tog:disabled { opacity: .45; cursor: default; }
.clear { border: 0; background: none; color: var(--accent2); cursor: pointer; font-size: 12px; font-weight: 600; }
.tc { display: grid; grid-template-columns: minmax(200px, 1.1fr) minmax(220px, 2.4fr) 132px minmax(170px, .9fr); gap: 18px; align-items: center; padding: 12px 4px; border-top: 1px solid var(--soft); }
.tc:first-child { border-top: 0; }
.tc .tp { color: var(--muted); font-size: 11px; }
.tc .sn { font-weight: 700; font-size: 14px; }
.tc .cx { color: var(--muted); font-size: 11px; margin-top: 2px; }
.ch { position: relative; height: 70px; }
.ch svg { width: 100%; height: 100%; display: block; overflow: visible; }
.ch .ax { position: absolute; left: -2px; font-size: 9.5px; color: var(--muted); transform: translate(-100%, -50%); }
.ch .lbl { position: absolute; bottom: -14px; font-size: 9.5px; color: var(--muted); }
.bars { height: 52px; }
.bars svg { width: 100%; height: 100%; display: block; }
.slot { margin-bottom: 6px; }
.slot .sl { display: block; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 2px; }
.slot .bs { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
.num .x { font-size: 15px; }
h3.sec { font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin: 22px 0 8px; }
.grid { overflow-x: auto; }
table.hg { border-collapse: separate; border-spacing: 2px; font-size: 11px; }
table.hg th.c { height: 130px; vertical-align: bottom; padding: 0 0 4px; font-weight: 600; color: var(--muted); }
table.hg th.c div { writing-mode: vertical-rl; transform: rotate(180deg); max-height: 126px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; width: 46px; text-align: left; margin: 0 auto; }
table.hg td { width: 46px; height: 24px; text-align: center; border-radius: 3px; font-variant-numeric: tabular-nums; cursor: default; }
table.hg td.cn { width: auto; text-align: left; padding-right: 10px; white-space: nowrap; }
table.hg tr.sr td { padding-top: 8px; font-weight: 700; color: var(--muted); text-align: left; font-size: 10.5px; text-transform: uppercase; letter-spacing: .04em; }
table.hg td.na { color: var(--border); }
table.hg td .m { font-size: 8px; vertical-align: top; margin-left: 1px; }
.country { cursor: pointer; color: var(--accent); font-weight: 600; border: 0; background: none; font-size: 12px; text-align: left; padding: 0; }
.country:hover { text-decoration: underline; }
.legend { color: var(--muted); font-size: 11px; margin-top: 6px; }
details.how { margin-top: 18px; color: var(--muted); font-size: 12px; }
details.how summary { cursor: pointer; font-weight: 600; color: var(--text); }
details.how li { margin: 4px 0 0 18px; }
@media (max-width: 900px) { .tc { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="top">
  <div>
    <h1>What is happening now</h1>
    <div class="sub" id="window"></div>
  </div>
  <div class="controls"><span id="seg"></span><select id="unit">__UNIT_OPTIONS__</select></div>
</div>
<div class="card" id="app"></div>
<script>__SHARED_JS__
const TOP = 12, GRID = 10;
const sel = document.getElementById('unit');
const open = new Set(), on = new Set();
const key = v => v.startsWith('region:') ? 'region' : v;
const FILTERS = [
    ['week', [['burst', 'Bursting'], ['elev', 'Elevated'], ['cool', 'Cooling']]],
    ['days', [['press', 'Pressing'], ['back', 'Came back'], ['quiet', 'Gone quiet']]],
];
const ratioOf = (s, k) => s && s.z[k] !== null && s.m[per] > 0 ? s.z[k] / s.m[per] : null;
const nowOf = s => ratioOf(s, s ? s.z.length - 1 : 0);

// Topics of a unit: its weekly rows (bursting, elevated, cooling) and the groups
// with a 7-day state, each tagged with the filters it matches.
function items(u) {
    const U = O.units[u];
    if (!U) return [];
    const map = new Map();
    for (const r of [...U.rows, ...U.fading]) map.set(r.g, {g: r.g, r});
    for (const g of Object.keys(U.beat.g)) {
        const bt = beat(u, g);
        if (map.has(g)) map.get(g).bt = bt;
        else if (BEAT_STATES[bt.state]) map.set(g, {g, bt});
    }
    return [...map.values()].map(it => {
        const b = it.r && it.r.b, tags = new Set();
        if (b && b[0] !== 'fade') tags.add('burst');
        if (b && b[0] === 'fade') tags.add('cool');
        if (it.r && it.r.p) tags.add('elev');
        if (it.bt && BEAT_STATES[it.bt.state]) tags.add(it.bt.state);
        // Articles above a usual week (this week) or above expected (7 days).
        const sc = Math.max(it.r ? score(it.r) : -Infinity, it.bt ? it.bt.n7 - it.bt.exp : -Infinity);
        const late = tags.size === 1 && tags.has('cool') || tags.has('quiet') && tags.size === 1;
        return {...it, tags, sc, late};
    }).sort((a, b) => a.late - b.late || b.sc - a.sc);
}

function chart(s) {
    const W = 520, H = 70, n = s ? s.z.length : 0;
    if (!n) return '<div class="ch"><div class="empty">No weekly index</div></div>';
    const v = s.z.map((_, k) => ratioOf(s, k));
    const top = Math.max(2, ...v.filter(x => x !== null).map(x => Math.min(x, 8)));
    const X = k => k / (n - 1) * W, Y = x => H - Math.min(x, top) / top * H;
    let d = '', pen = false;
    v.forEach((x, k) => { if (x === null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${X(k).toFixed(1)},${Y(x).toFixed(1)}`; pen = true; });
    const burst = new Set(s.f || []);
    const ticks = [...burst].map(k => `<rect x="${X(k) - 2}" y="${H - 4}" width="4" height="4" fill="var(--red)"/>`).join('');
    const tips = v.map((x, k) => `<rect x="${X(k) - W / n / 2}" y="0" width="${W / n}" height="${H}" fill="transparent"><title>Week to ${fmtDay(weekEnd(k), {year: 'numeric'})}: ${fx(x)} usual${burst.has(k) ? ' · bursting' : ''}</title></rect>`).join('');
    const last = v[n - 1];
    return `<div class="ch"><span class="ax" style="top:${Y(1)}px">1×</span><span class="ax" style="top:0">${fx(top)}${v.some(x => x > top) ? '+' : ''}</span>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <line x1="0" x2="${W}" y1="${Y(1)}" y2="${Y(1)}" stroke="var(--border)" stroke-dasharray="4 3" vector-effect="non-scaling-stroke"/>
        ${ticks}<path d="${d}" fill="none" stroke="var(--accent)" stroke-width="1.6" vector-effect="non-scaling-stroke"/>
        ${last !== null ? `<rect x="${X(n - 1) - 3}" y="${Y(last) - 3}" width="6" height="6" fill="var(--accent)"/>` : ''}${tips}
      </svg><span class="lbl" style="left:0">${fmtDay(weekEnd(0), {year: 'numeric'})}</span><span class="lbl" style="right:0">${fmtDay(weekEnd(n - 1))}</span></div>`;
}

function bars(bt) {
    if (!bt) return '<div class="bars"></div>';
    const W = 132, H = 52, bw = W / 7, e = bt.exp / 7;
    const top = Math.max(1, e, ...bt.win.map(x => x || 0));
    const out = bt.win.map((x, k) => {
        const day = fmtDay(dayOf(bt.idx[k]), {weekday: 'short'});
        const h = (x || 0) / top * (H - 12);
        const fill = x === null ? 'url(#hatch)' : 'var(--accent)';
        return `<rect x="${k * bw + 2}" y="${H - 12 - (x === null ? H - 12 : h)}" width="${bw - 4}" height="${x === null ? H - 12 : Math.max(h, x > 0 ? 1 : 0)}" fill="${fill}" opacity="${k === 6 ? 1 : .75}"><title>${day}: ${x === null ? 'excluded (suspect source dump)' : arts(x)}</title></rect>
            <text x="${k * bw + bw / 2}" y="${H - 1}" font-size="8.5" text-anchor="middle" fill="var(--muted)">${day.slice(0, 1)}</text>`;
    }).join('');
    const ey = H - 12 - e / top * (H - 12);
    return `<div class="bars"><svg viewBox="0 0 ${W} ${H}"><defs><pattern id="hatch" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="1" height="3" fill="var(--border)"/></pattern></defs>
      ${out}<line x1="0" x2="${W}" y1="${ey}" y2="${ey}" stroke="var(--red)" stroke-dasharray="3 2" stroke-width="1"><title>Expected per day: ${e.toFixed(1)}</title></line></svg></div>
      <div class="pace">${bt.n7.toLocaleString('en')} in 7 days · ${Math.round(bt.exp).toLocaleString('en')} expected</div>`;
}

function card(u, it) {
    const [topic, sub] = parts(it.g), r = it.r, s = O.units[u].s[it.g];
    const extra = [r && r.c && r.c.length ? esc(r.c.join(', ')) : '', r && r.in && r.in.length ? 'Bursting in ' + r.in.slice(0, 4).map(name).map(esc).join(', ') + (r.in.length > 4 ? ` +${r.in.length - 4}` : '') : ''].filter(Boolean);
    const now = r ? (r.u ? null : r.r[per]) : nowOf(s);
    const wb = weekBadges(r);
    return `<div class="tc">
      <div><div class="tp">${esc(topic)}</div><div class="sn">${esc(sub)}</div>${extra.map(x => `<div class="cx">${x}</div>`).join('')}</div>
      ${chart(s)}
      <div>${bars(it.bt)}</div>
      <div>
        <div class="num"><span class="x">${fx(now)} usual</span> <span class="n">${r ? arts(r.n) + ' this week' : ''}</span></div>
        <div class="slot"><span class="sl">${weekLabel()}</span><span class="bs">${wb.join('') || '<span class="pace">No burst</span>'}</span></div>
        <div class="slot"><span class="sl">Last 7 days, to ${lastDay()}</span><span class="bs">${stateBadge(it.bt) || '<span class="pace">Not mentioned</span>'}</span></div>
      </div></div>`;
}

function kpis(u, list) {
    const k = O.units[u].kpi, usual = k.usual[per], d = usual ? (k.articles / usual - 1) * 100 : null;
    const b = O.units[u].beat, t = todayIdx();
    const a7 = b.a.slice(Math.max(0, t - 6), t + 1).reduce((s, x) => s + (x || 0), 0);
    const cnt = tag => list.filter(x => x.tags.has(tag)).length;
    const members = u === 'region' ? Object.values(O.subregions).flat() : u.startsWith('subregion:') ? O.subregions[u.slice(10)] : null;
    return `<div class="kpis">
      <div class="kpi"><div class="v">${k.articles.toLocaleString('en')}</div><div class="t">articles, ${weekLabel().replace('Week of ', '')}</div>${d === null ? '' : `<div class="d ${d >= 0 ? 'up' : 'down'}">${d >= 0 ? '+' : ''}${d.toFixed(0)}% vs avg week (${PERIODS[per][1]})</div>`}</div>
      <div class="kpi"><div class="v">${a7.toLocaleString('en')}</div><div class="t">articles, last 7 days to ${lastDay()}</div></div>
      <div class="kpi"><div class="v">${cnt('burst')}</div><div class="t">topics bursting${members ? ' in at least one country' : ''}</div></div>
      <div class="kpi"><div class="v">${cnt('press')}</div><div class="t">topics pressing</div></div>
      ${members ? `<div class="kpi"><div class="v">${k.countries}<small> / ${members.length}</small></div><div class="t">countries with a burst</div></div>` : ''}
    </div>`;
}

function filters(list) {
    const cnt = tag => list.filter(x => x.tags.has(tag)).length;
    const lab = {week: weekLabel(), days: `Last 7 days, to ${lastDay()}`};
    return `<div class="filters">${FILTERS.map(([grp, fs]) => `<div class="fg"><span>${lab[grp]}</span>${fs.map(([t, l]) =>
        `<button class="tog ${on.has(t) ? 'on' : ''}" data-t="${t}" ${cnt(t) ? '' : 'disabled'}>${l}<b>${cnt(t)}</b></button>`).join('')}</div>`).join('')}
      ${on.size ? '<button class="clear">Show all</button>' : ''}</div>`;
}

// Countries x the unit's top topics: x usual this week, burst (●) and pressing (▲) marks.
function grid(u, list) {
    const subs = u === 'region' ? Object.keys(O.subregions) : u.startsWith('subregion:') ? [u.slice(10)] : [];
    const cols = list.filter(x => O.units[u].s[x.g]).slice(0, GRID).map(x => x.g);
    if (!subs.length || !cols.length) return '';
    const cell = (c, g) => {
        const U = O.units[c], s = U && U.s[g], v = nowOf(s);
        if (v === null) return `<td class="na" title="${esc(name(c))} · ${esc(parts(g)[1])}: no index">·</td>`;
        const r = [...U.rows, ...U.fading].find(x => x.g === g), bt = beat(c, g);
        const burst = r && r.b && r.b[0] !== 'fade', press = bt && bt.state === 'press';
        const a = Math.min(1, Math.abs(Math.log2(Math.max(v, 1e-3))) / 2);
        const bg = v >= 1 ? `rgba(218,30,40,${(a * .85).toFixed(2)})` : `rgba(22,154,243,${(a * .35).toFixed(2)})`;
        return `<td style="background:${bg};color:${v >= 1 && a > .6 ? '#fff' : 'var(--text)'}" title="${esc(name(c))} · ${esc(parts(g)[1])}: ${fx(v)} usual${burst ? ' · bursting' : ''}${press ? ' · pressing' : ''}">${fx(v).replace('×', '')}${burst ? '<span class="m">●</span>' : ''}${press ? '<span class="m">▲</span>' : ''}</td>`;
    };
    const rows = subs.map(sr => {
        const cs = O.subregions[sr].filter(c => O.units[c]).sort((a, b) => cols.reduce((t, g) => t + (nowOf(O.units[b].s[g]) || 0) - (nowOf(O.units[a].s[g]) || 0), 0));
        return (subs.length > 1 ? `<tr class="sr"><td colspan="${cols.length + 1}">${esc(name(sr))}</td></tr>` : '')
            + cs.map(c => `<tr><td class="cn"><button class="country" data-c="${c}">${esc(name(c))}</button></td>${cols.map(g => cell(c, g)).join('')}</tr>`).join('');
    }).join('');
    return `<h3 class="sec">Countries × top topics, ${weekLabel().replace('Week of ', 'week of ')}</h3>
      <div class="grid"><table class="hg"><tr><th></th>${cols.map(g => `<th class="c"><div title="${esc(O.labels[g] || g)}">${esc(parts(g)[1])}</div></th>`).join('')}</tr>${rows}</table></div>
      <div class="legend">Cell = × usual this week (red above, blue below; Compare with sets "usual"). ● bursting this week · ▲ pressing in the last 7 days · "·" no index. Click a country to open it.</div>`;
}

const HOW = `<details class="how"><summary>How to read this</summary><ul>
  <li><b>× usual</b>: the weekly Baker index (each source's share of articles standardized by its 2024 variation, averaged over sources that published in at least half of 2024's weeks; regions average their countries) over its average in the comparison period. 1× = a usual week; "–" = none of those sources covers it.</li>
  <li><b>Chart</b>: the last 52 weeks; dashed line = usual; red ticks = weeks it burst (in at least one country, for a region).</li>
  <li><b>Bursting</b>: weekly count ≥ 2.5× expected from its trailing 26-week share, ≥ 5 articles, Poisson p < 1e-4, per country. <b>Elevated N wks</b>: the 4-week average has stayed 1.5× its 2024 level for N weeks (long crises stop bursting). <b>Cooling</b>: stopped bursting in the last 3 weeks.</li>
  <li><b>Last 7 days</b>: the 7 UTC days up to the newest article. Bars = articles per day, dashed red = expected per day (a usual week of the comparison period, scaled by this unit's articles in those 7 days). <b>Pressing</b>: on ≥ 2 of the last 3 days, ≥ 1.5× expected, ≥ 5 articles. <b>Came back</b>: none in the 14 days before, ≥ 10 articles in 2024. <b>Gone quiet</b>: bursting or elevated in the last 4 weeks, none in 7 days.</li>
  <li>Topics rank by articles above a usual week (or above expected, for the last 7 days). Toggles show topics matching any of those picked.</li></ul></details>`;

function render() {
    document.getElementById('window').textContent = `${weekLabel()} · last 7 days to ${lastDay()} UTC (newest article) · ${asofText()}`;
    document.getElementById('seg').innerHTML = `<div class="seg"><span>Compare with</span>${PERIODS.map(([, t], i) => `<button data-p="${i}" class="${i === per ? 'on' : ''}">${t}</button>`).join('')}</div>`;
    const u = key(sel.value), U = O.units[u];
    if (!U) { document.getElementById('app').innerHTML = '<div class="empty">No data for this unit.</div>'; return; }
    const all = items(u);
    const shown = on.size ? all.filter(x => [...on].some(t => x.tags.has(t))) : all;
    const k = 'cards:' + u, list = open.has(k) ? shown : shown.slice(0, TOP);
    document.getElementById('app').innerHTML = kpis(u, all) + filters(all)
        + (list.length ? list.map(it => card(u, it)).join('') : '<div class="empty">No topic matches.</div>')
        + (shown.length > TOP ? `<button class="more" data-k="${k}">${open.has(k) ? 'Show top ' + TOP : 'Show all ' + shown.length}</button>` : '')
        + grid(u, shown) + HOW;
    document.querySelectorAll('.seg button').forEach(b => b.onclick = () => { per = +b.dataset.p; render(); });
    document.querySelectorAll('.tog').forEach(b => b.onclick = () => { on.has(b.dataset.t) ? on.delete(b.dataset.t) : on.add(b.dataset.t); render(); });
    document.querySelectorAll('.clear').forEach(b => b.onclick = () => { on.clear(); render(); });
    document.querySelectorAll('.more').forEach(b => b.onclick = () => { open.has(b.dataset.k) ? open.delete(b.dataset.k) : open.add(b.dataset.k); render(); });
    document.querySelectorAll('.country').forEach(b => b.onclick = () => { sel.value = b.dataset.c; render(); window.scrollTo(0, 0); });
}
sel.onchange = render;
render();
</script>
</body>
</html>"""


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def unit_names(region_subtree: list) -> dict:
    """Display names of the region, its subregions and countries, by slug."""
    out = {}
    for r in region_subtree:
        out[r["slug"]] = r["label"]
        for s in r.get("children", []):
            out[s["slug"]] = s["label"]
            out.update({c["slug"]: c["label"] for c in s.get("children", [])})
    return out


def _page(template: str, overview: dict, names: dict) -> str:
    return (
        template.replace("__SHARED_CSS__", SHARED_CSS)
        .replace("__SHARED_JS__", SHARED_JS)
        .replace("__NAMES_JSON__", _json(names))
        .replace("__OVERVIEW_JSON__", _json(overview))
    )


def build_overview_html(overview: dict, unit_options_html: str, names: dict) -> str:
    return _page(
        OVERVIEW_TEMPLATE.replace("__UNIT_OPTIONS__", unit_options_html),
        overview,
        names,
    )
