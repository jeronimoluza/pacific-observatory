"""The concepts dashboard's Overview tab: what is happening now, per unit.

Read ``outputs/text/<region>/overview.json`` (written by
``src/text/analysis/explorations/overview.py``). A dropdown picks the region,
a subregion or a country; the baseline T1 is 2024.

Per unit: two KPIs (articles in the database, last 7 days) and one ranked
list of story cards. Every topic, subtopic and theme has a Baker index of the
last 4 weeks on the monthly index's scale with T1 as its baseline (``q``, x
usual) and is ranked by how far
that sits above usual in counting noise, (n - n/q) / sqrt(n/q) for its n
articles. A topic whose articles mostly also mention a bigger topic (``co``:
same articles, overview.py) belongs to that topic's card; going down the
ranking, each card is led by the biggest topic its first topic belongs to
and pulls in the topics belonging there, those sharing a concept with it,
then the parents and subtopics of everything in the card. A card ranks by
its strongest topic; its lines are sorted by x usual and it opens on the first.

A card gives the focused topic's x usual and the last calendar month at or
above it ("highest since"), a rising or cooling flag from the weekly index,
the countries furthest above usual (region and subregions) and its driving
concepts. Every card has one chart, the focused topic thick and its concepts
thin, in three sections: 4-week blocks counted back from the last day with
data or calendar months (a page toggle) from January 2024 to a draggable
line, the 4 weeks to each week from there to the last day (read with the
blocks' sigma and mean), and an empty "this week" band.

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
.more { border: 0; background: none; color: var(--accent2); cursor: pointer; font-size: 12px; padding: 6px 0 0; font-weight: 600; }
.empty { color: var(--muted); padding: 12px 0; }
"""

SHARED_JS = r"""
const O = __OVERVIEW_JSON__;
const NAMES = __NAMES_JSON__;
const per = 0;  // T1: 2024, the first of each per-window array
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const name = u => NAMES[u] || u.replace(/_/g, ' ').replace(/\b./g, x => x.toUpperCase());
const parts = g => { const l = O.labels[g] || g; const i = l.indexOf(' · '); return i < 0 ? ['', l] : [l.slice(0, i), l.slice(i + 3)]; };
const fx = v => v === null || !isFinite(v) ? '–' : (v >= 10 ? Math.round(v) : v.toFixed(1)) + '×';
const arts = n => `${n.toLocaleString('en')} article${n === 1 ? '' : 's'}`;
const DAY = 864e5;
const fmtDay = (d, o = {}) => new Date(typeof d === 'string' ? d + 'T00:00:00Z' : d).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC', ...o});
const fmtMonth = t => fmtDay(t, {day: undefined, month: 'short', year: 'numeric'});
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
.kpi .t { color: var(--muted); font-size: 12px; }
.tc { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(280px, 2.4fr); gap: 22px; align-items: start; padding: 16px 4px; border-top: 1px solid var(--soft); }
.tc:first-child { border-top: 0; }
.tc .tp { color: var(--muted); font-size: 11px; }
.tc .sn { font-weight: 700; font-size: 14px; }
.tc .hl { font-size: 22px; font-weight: 700; color: var(--accent); margin-top: 6px; }
.tc .hl span { font-size: 12px; font-weight: 400; color: var(--muted); }
.tc .h2 { font-size: 12px; color: var(--muted); margin-top: 2px; }
.tr { font-size: 10px; font-weight: 600; border-radius: 8px; padding: 1px 6px; margin-left: 4px; white-space: nowrap; }
.tr.up { background: #fde8e9; color: var(--red); }
.tr.dn { background: var(--soft); color: var(--muted); }
.tc .hd { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .04em; margin-top: 10px; }
.chip { display: inline-block; border: 1px solid var(--border); background: #fff; color: var(--text); border-radius: 12px; padding: 1px 8px; margin: 3px 3px 0 0; font-size: 11px; cursor: pointer; font-variant-numeric: tabular-nums; }
.chip:hover { border-color: var(--accent2); }
.chip.dc { cursor: default; }
.ask { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 14px; margin-bottom: 12px; }
.chip.dc:hover { border-color: var(--border); }
.lg { display: flex; flex-wrap: wrap; gap: 2px 12px; margin-top: 20px; }
.lg button { border: 0; background: none; cursor: pointer; font-size: 11px; color: var(--text); padding: 1px 0; display: inline-flex; align-items: center; gap: 4px; opacity: .55; }
.lg button.on { opacity: 1; font-weight: 600; }
.lg i { display: inline-block; width: 12px; height: 3px; border-radius: 2px; }
.lg i.hd { width: 7px; height: 7px; border-radius: 50%; margin-right: -2px; }
.cl2 { margin-top: 8px; display: grid; gap: 7px; }
.ci { display: grid; grid-template-columns: 14px 1fr; gap: 6px; align-items: start; }
.ci > i { width: 14px; height: 3px; border-radius: 2px; margin-top: 9px; }
.cn1 { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.cn1 b { font-size: 14px; font-weight: 700; }
.cn1 .cx { font-size: 16px; font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; }
.cn1 .cnn { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
.cin { font-size: 11px; color: var(--muted); }
.tls { display: flex; flex-wrap: wrap; gap: 2px 12px; font-size: 11.5px; color: var(--muted); }
.tls b { font-weight: 600; color: var(--text); }
.c3 { margin: 4px 0 18px 30px; }
.c3 .pl { position: relative; height: 170px; touch-action: none; }
.c3 svg { width: 100%; height: 100%; display: block; overflow: visible; }
.c3 .ya { position: absolute; left: -6px; transform: translate(-100%, -50%); font-size: 9.5px; color: var(--muted); }
.c3 .xa { position: absolute; bottom: -15px; transform: translateX(-50%); font-size: 9.5px; color: var(--muted); white-space: nowrap; }
.c3 .xa.r { transform: translateX(calc(-100% - 3px)); }
.c3 .d1 { position: absolute; top: 0; bottom: 0; width: 12px; transform: translateX(-50%); cursor: ew-resize; z-index: 1; }
.c3 .xh { display: none; position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px solid var(--muted); pointer-events: none; }
.c3 .xd { display: none; position: absolute; bottom: -16px; transform: translateX(-50%); font-size: 10px; font-weight: 600; color: var(--text); background: var(--soft); border-radius: 3px; padding: 0 4px; white-space: nowrap; pointer-events: none; z-index: 1; }
.c3 .tt { display: none; position: absolute; bottom: calc(100% + 6px); background: var(--panel); border: 1px solid var(--border); border-radius: 6px; padding: 4px 8px; font-size: 11px; box-shadow: 0 2px 8px rgba(0,0,0,.08); pointer-events: none; z-index: 3; white-space: nowrap; }
.c3 .tt td { padding: 1px 4px; }
.c3 .tt i { display: block; width: 12px; border-radius: 2px; }
.c3 .tt .x { text-align: right; font-size: 11px; }
.c3.on .xh, .c3.on .xd, .c3.on .tt { display: block; }
.country { cursor: pointer; }
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
  <div class="controls"><span class="seg" id="view"><span>Chart</span><button data-v="4w" class="on">4-week</button><button data-v="cal">calendar</button></span><select id="unit">__UNIT_OPTIONS__</select></div>
</div>
<div class="ask" id="ask"></div>
<div class="card" id="app"></div>
<script>__SHARED_JS__
const TOP = 12;
const sel = document.getElementById('unit');
const open = new Set(), focus = new Map();
const key = v => v.startsWith('region:') ? 'region' : v;
const sub = g => parts(g)[1];
const weekTo = () => fmtDay(O.week);

// Calendar months counted back from the week's end ("highest since").
const END = Date.parse(O.week + 'T00:00:00Z');
const monthStart = (k, n) => { const d = new Date(END); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - (n - 1 - k), 1); };

// Concepts lead each card: the keywords driving its topics (the concepts
// with the most articles above a usual week this week, at most CONCEPTS),
// each on its own Baker index (the same rule as the topics). The text lists
// them with their x usual and the card topics they belong to; the chart draws
// them as thin lines next to the card's topic.
const CONCEPTS = 5, CCOL = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];
function cardConcepts(u, lines) {
    const U = O.units[u], cs = [];
    for (const g of lines) for (const [c] of U.dc[g] || []) if (!cs.includes(c) && U.s['c:' + c]) cs.push(c);
    const S = c => U.s['c:' + c];
    return cs.sort((a, b) => (S(b).q[per] ?? -1) - (S(a).q[per] ?? -1)).slice(0, CONCEPTS);
}
// The card topics a concept belongs to: its group (or the group's parent)
// and the themes listing it.
const topicsOf = (c, lines) => lines.filter(g => g === O.cgroup[c] || (O.kids[g] || []).includes(O.cgroup[c]) || (themeOf(g) && themeOf(g).members.includes(c)));

// The chart, x usual with 2024 as T1, in three sections split by two dashed
// lines, each section keeping its width: (1) from January 2024 to line 1,
// the 4-week blocks counted back from t0 (the last day with data) or the
// calendar months (Baker's monthly); (2) from line 1 to t0, the 4 weeks to
// each week, read with the blocks' sigma and mean (on a block's last day it
// is that block); (3) this week, empty for now. A point sits on its
// period's last day. Dragging line 1 moves the date it stands for, on every
// card (in the 4-week view, to a block's end).
const T0 = Date.parse(O.data_end + 'T00:00:00Z'), JAN = Date.UTC(2024, 0, 1), WK = 7 * DAY;
const NM = Math.floor((T0 - Date.UTC(2024, 0, 28)) / WK) + 1;  // weekly points (overview.py)
const SHARE = [.46, .46], CW = 600, CHH = 170;
let view = '4w', cut = 12;  // weeks from line 1 to t0
const CHARTS = {};
const cutW = () => view === '4w' ? Math.max(4, Math.round(cut / 4) * 4) : cut;
function xmap() {
    const L = T0 - cutW() * WK, a = SHARE[0] * CW, b = (SHARE[0] + SHARE[1]) * CW;
    return {L, a, b, X: t => t <= L ? (t - JAN) / (L - JAN) * a : a + (t - L) / (T0 - L) * (b - a),
        T: x => x <= a ? JAN + x / a * (L - JAN) : L + (x - a) / (b - a) * (T0 - L)};
}
// A line's points per section: {t, x (x 100), n (articles)}.
function pts(s, L) {
    const nb = s.b4.length, nm = s.m4.length;
    const one = view === '4w'
        ? s.b4.map((x, j) => ({t: T0 - (nb - 1 - j) * 4 * WK, x, n: s.n4[nm - 1 - (nb - 1 - j) * 4]}))
        : s.mo.map((x, j) => ({t: Date.UTC(2024, j + 1, 1) - DAY, x, n: s.nm[j]}));
    const two = s.m4.map((x, j) => ({t: T0 - (nm - 1 - j) * WK, x, n: s.n4[j]}));
    return [one.filter(p => p.t <= L), two.filter(p => p.t >= L)];
}
function c3(u, id, f, cs) {
    const U = O.units[u];
    CHARTS[id] = [{s: U.s[f], n: sub(f), col: 'var(--accent)', w: 2.6, cnt: count(f)},
        ...cs.map((c, i) => ({s: U.s['c:' + c], n: O.clabels[c], col: CCOL[i], w: 1.4, cnt: arts}))];
    return `<div class="c3" data-id="${esc(id)}"><div class="pl">${plot(id)}</div></div>`;
}
function plot(id) {
    const C = CHARTS[id], M = xmap(), P = C.map(l => pts(l.s, M.L));
    const xs = P.flat(2).map(p => p.x).filter(x => x !== null);
    const max = Math.max(100, ...xs) / 100;
    const step = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000].find(v => v >= max / 5) || Math.ceil(max / 5);
    const top = Math.max(2, Math.ceil(max / step) * step), Y = x => CHH - x / top * CHH;
    const grid = [];
    for (let v = step; v <= top; v += step) grid.push(v);
    if (!grid.includes(1)) grid.push(1);
    const path = ps => { let d = '', pen = false; for (const p of ps) { if (p.x === null) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${M.X(p.t).toFixed(1)},${Y(p.x / 100).toFixed(1)}`; pen = true; } return d; };
    const pc = x => (x / CW * 100).toFixed(2) + '%';
    const xl = [];
    for (let k = 0; ; k++) {  // section 1: quarters
        const a = Date.UTC(2024, 3 * k, 1), b = Math.min(Date.UTC(2024, 3 * k + 3, 1), M.L);
        if (a >= M.L) break;
        if (M.X(b) - M.X(a) >= 22) xl.push([(M.X(a) + M.X(b)) / 2, `Q${k % 4 + 1} '${String(24 + Math.floor(k / 4)).padStart(2, '0')}`]);
    }
    // Section 2: every 4 weeks back from t0 (every 8, 12... when they would crowd).
    const by = 4 * WK * Math.ceil(30 / (M.X(T0) - M.X(T0 - 4 * WK)));
    for (let t = T0 - by; t >= M.L; t -= by) if (M.X(t) - M.a >= 18 && M.X(T0) - M.X(t) >= 30) xl.push([M.X(t), fmtDay(t)]);
    xl.push([M.b, fmtDay(T0), 'r'], [(M.b + CW) / 2, 'this week']);
    const vl = x => `<line x1="${x}" x2="${x}" y1="0" y2="${CHH}" stroke="var(--muted)" stroke-dasharray="4 3" vector-effect="non-scaling-stroke"/>`;
    return `${[0, ...grid].filter(v => v !== 1 || step === 1 || Y(0) - Y(1) >= 12).map(v => `<span class="ya" style="top:${(Y(v) / CHH * 100).toFixed(1)}%">${v ? v + '×' : 0}</span>`).join('')}
      ${xl.map(([x, t, r]) => `<span class="xa${r ? ' r' : ''}" style="left:${pc(x)}">${t}</span>`).join('')}
      <svg viewBox="0 0 ${CW} ${CHH}" preserveAspectRatio="none">
        <rect x="${M.b}" y="0" width="${CW - M.b}" height="${CHH}" fill="var(--soft)" opacity=".6"/>
        <line x1="0" x2="${CW}" y1="${CHH}" y2="${CHH}" stroke="var(--border)" vector-effect="non-scaling-stroke"/>
        ${grid.map(v => `<line x1="0" x2="${M.b}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" stroke="var(--border)" ${v === 1 ? 'stroke-dasharray="4 3"' : 'opacity=".55"'} vector-effect="non-scaling-stroke"/>`).join('')}
        ${C.map((l, i) => P[i].map(ps => `<path d="${path(ps)}" fill="none" stroke="${l.col}" stroke-width="${l.w}" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`).join('')).reverse().join('')}
        ${vl(M.a)}${vl(M.b)}
      </svg><i class="xh"></i><span class="xd"></span><div class="tt"></div>
      <div class="d1" style="left:${pc(M.a)}" title="Drag: where the weekly view starts"></div>`;
}
const redraw = () => document.querySelectorAll('.c3').forEach(el => { el.querySelector('.pl').innerHTML = plot(el.dataset.id); });
// Hover: a line at the mouse, the nearest period highlighted on the x axis
// and its values in a table above the chart.
function onMove(e) {
    const pl = !drag && e.target.closest ? e.target.closest('.c3 .pl') : null;
    document.querySelectorAll('.c3.on').forEach(x => { if (!pl || x !== pl.parentElement) x.classList.remove('on'); });
    if (!pl) return;
    const C = CHARTS[pl.parentElement.dataset.id], r = pl.getBoundingClientRect(), M = xmap();
    const x = Math.min(Math.max((e.clientX - r.left) / r.width * CW, 0), CW);
    const xh = pl.querySelector('.xh'), xd = pl.querySelector('.xd'), tt = pl.querySelector('.tt');
    xh.style.left = x / CW * 100 + '%';
    pl.parentElement.classList.add('on');
    if (x > M.b) { xd.textContent = 'this week'; xd.style.left = (M.b + CW) / 2 / CW * 100 + '%'; tt.style.visibility = 'hidden'; return; }
    const sec = x <= M.a ? 0 : 1, P = C.map(l => pts(l.s, M.L)[sec]), t = M.T(x);
    if (!P[0].length) return;
    let k = 0;
    P[0].forEach((p, j) => { if (Math.abs(p.t - t) < Math.abs(P[0][k].t - t)) k = j; });
    const p0 = P[0][k];
    xd.textContent = sec === 0 && view === 'cal' ? fmtMonth(p0.t) : `4 weeks to ${fmtDay(p0.t, {year: 'numeric'})}`;
    xd.style.left = M.X(p0.t) / CW * 100 + '%';
    tt.innerHTML = '<table>' + C.map((l, i) => { const p = P[i][k]; return `<tr><td><i style="background:${l.col};height:${l.w > 2 ? 4 : 2}px"></i></td><td>${esc(l.n)}</td><td class="x">${p.x === null ? '–' : fx(p.x / 100)}</td><td class="n">${p.n == null ? '' : l.cnt(p.n)}</td></tr>`; }).join('') + '</table>';
    tt.style.visibility = '';
    const w = tt.offsetWidth, cx = x / CW * r.width;
    tt.style.left = Math.min(Math.max(cx - w / 2, 0), Math.max(0, r.width - w)) + 'px';
}
let drag = null;
document.addEventListener('mousemove', onMove);
document.documentElement.addEventListener('mouseleave', () => document.querySelectorAll('.c3.on').forEach(x => x.classList.remove('on')));
document.addEventListener('pointerdown', e => {
    const h = e.target.closest && e.target.closest('.d1');
    if (!h) return;
    drag = {r: h.parentElement.getBoundingClientRect(), M: xmap()};
    document.querySelectorAll('.c3.on').forEach(x => x.classList.remove('on'));
    e.preventDefault();
});
document.addEventListener('pointermove', e => {
    if (!drag) return;
    const x = Math.min(Math.max((e.clientX - drag.r.left) / drag.r.width * CW, 0), drag.M.b);
    const c = Math.min(Math.max(Math.round((T0 - drag.M.T(x)) / WK), 4), NM - 9), w = cutW();
    cut = c;
    if (cutW() !== w) redraw();
});
document.addEventListener('pointerup', () => { drag = null; });

// Stories: every topic, subtopic and theme ranked together by how far its
// last 4 weeks' Baker index (q, x usual, the comparison period as T1) sits
// above usual in counting noise: its n articles against the n / q a usual 4
// weeks would have, (n - n/q) / sqrt(n/q). A topic qualifies with >= N_MIN
// articles from >= MIN_SOURCES sources in those days and either >= Z_MIN or
// a state.
// Grouping: a topic's home is the topic >= Z_MIN, among the bigger ones
// most of its articles also mention (U.co), with the highest lift; its
// root follows homes up. Going down the ranking, a topic not yet placed
// opens a story led by its root, which pulls in every topic with that root,
// those sharing a concept with the root or the first topic (a theme's
// members, a group's and its subgroups' concepts), then the parents and
// subtopics of everything in the story. A story ranks by its first topic
// (its strongest); its lines are sorted by x usual and it opens on the first.
const Z_MIN = 3, N_MIN = 10, MIN_SOURCES = 3, LINES = 6;
const above = (q, n) => q > 0 && n ? (n - n / q) / Math.sqrt(n / q) : -Infinity;
const mentions = n => `${n.toLocaleString('en')} mention${n === 1 ? '' : 's'}`;
const count = g => g.startsWith('t:') ? mentions : arts;
const parentOf = {};
for (const [p, ks] of Object.entries(O.kids)) for (const k of ks) parentOf[k] = p;
const themeOf = g => g.startsWith('t:') ? O.themes[+g.slice(2)] : null;
const conceptsOf = g => new Set(themeOf(g) ? themeOf(g).members : [g, ...(O.kids[g] || [])].flatMap(x => O.gconcepts[x] || []));

function topics(u) {
    const U = O.units[u], rows = new Map([...U.rows, ...U.fading].map(r => [r.g, r]));
    return Object.keys(U.s).filter(g => !g.startsWith('c:')).map(g => {
        const s = U.s[g], r = rows.get(g), bt = U.beat.g[g] ? beat(u, g) : null, tags = new Set();
        if (r && r.b && r.b[0] !== 'fade') tags.add('burst');
        if (r && r.b && r.b[0] === 'fade') tags.add('cool');
        if (r && r.p) tags.add('elev');
        if (g.startsWith('t:') && s.b) tags.add('burst');
        if (bt && BEAT_STATES[bt.state]) tags.add(bt.state);
        return {g, n: s.nd, ns: s.ns, q: s.q[per] === null ? 0 : s.q[per], z: above(s.q[per], s.nd), tags, cs: conceptsOf(g)};
    });
}

const kin = (a, b) => parentOf[a.g] === b.g || parentOf[b.g] === a.g;
const shares = (a, b) => [...a.cs].some(c => b.cs.has(c));

function stories(u) {
    const live = topics(u).filter(t => t.n >= N_MIN && t.ns >= MIN_SOURCES && (t.z >= Z_MIN || t.tags.size)).sort((a, b) => b.z - a.z);
    const byG = new Map(live.map(t => [t.g, t])), co = O.units[u].co || {};
    const home = g => (co[g] || []).filter(([b]) => byG.has(b) && byG.get(b).z >= Z_MIN).sort((a, b) => b[2] - a[2])[0] || null;
    const root = g => { const seen = new Set([g]); let h; while ((h = home(g)) && !seen.has(h[0])) { g = h[0]; seen.add(g); } return g; };
    const used = new Set(), out = [];
    for (const t of live) {
        if (used.has(t.g)) continue;
        const r = byG.get(root(t.g));
        if (used.has(r.g)) continue;
        const lines = [r, ...live.filter(o => o !== r && !used.has(o.g) && root(o.g) === r.g)];
        lines.forEach(o => used.add(o.g));
        const take = ok => { for (const o of live) if (!used.has(o.g) && ok(o)) { lines.push(o); used.add(o.g); } };
        take(o => shares(r, o) || shares(t, o));
        for (let k = 0; k < lines.length; k++) take(o => kin(lines[k], o));
        const tags = new Set(lines.flatMap(x => [...x.tags]));
        lines.sort((a, b) => b.z - a.z);  // the card opens on the line that ranks it
        out.push({lead: r, lines, tags, late: [...tags].every(x => x === 'cool' || x === 'quiet')});
    }
    return out.sort((a, b) => a.late - b.late);  // stable: the ranking otherwise
}

// A topic's place: theme (with the headings it spans) or heading (and parent).
function where(g) {
    const t = themeOf(g);
    if (t) return 'Theme · ' + t.headings.join(' · ');
    return parts(g)[0] + (parentOf[g] ? ' · in ' + sub(parentOf[g]) : '');
}

// "Highest since": the last complete calendar month at or above the last 4
// weeks, when that is before last month (null: none since 2015).
function since(s) {
    const hs = s.hs[per];
    if (hs === null) return ' · highest since 2015';
    const t = Date.parse(hs + '-01T00:00:00Z');
    return t < monthStart(0, 2) ? ` · highest since ${fmtMonth(t)}` : '';
}

// The other comparison, from the same index: the last 4 weeks against the
// past 12 months (change); and how long the monthly index has run at >= 1.5x
// its 2024 level, counting back from the last complete month (>= 2 months,
// back to January 2024 at most: the chart's months).
function also(s) {
    const x = s.q[1];
    const vs = x === null ? '' : `${fx(x)} the past 12 months`;
    const m = s.mo, n = m.length;
    let k = 0;
    while (k < n && m[n - 1 - k] !== null && m[n - 1 - k] >= 150) k++;
    const run = k < 2 ? '' : `above 1.5× its 2024 level since ${fmtMonth(Date.UTC(2024, n - k, 1))}`;
    return [vs, run].filter(Boolean).join(' · ');
}

function storyCard(u, st) {
    const U = O.units[u], ck = u + st.lead.g;
    const lines = st.lines.slice(0, LINES).map(x => x.g);
    const f = lines.includes(focus.get(ck)) ? focus.get(ck) : lines[0];
    const s = U.s[f], q = s.q[per];
    const tr = s.tr === 1 ? '<span class="tr up">rising this week</span>' : s.tr === -1 ? '<span class="tr dn">cooling this week</span>' : '';
    const w = (s.w || [])[per] || [];
    const where_ = w.length ? `<div class="hd">Where</div>${w.map(([c, x, n]) => `<button class="chip country" data-c="${c}" title="${count(f)(n)} in the 4 weeks to ${weekTo()}">${esc(name(c))} ${fx(x)} · ${count(f)(n)}</button>`).join('')}` : '';
    const cs = cardConcepts(u, lines);
    if (!cs.length) {  // no driving concepts: the topic's text
        const head = q === null ? '<div class="hl">No usual level to compare with</div>'
            : `<div class="hl">${fx(q)} <span>usual, last 4 weeks · ${count(f)(s.nd)}${q >= 1 ? since(s) : ''}</span></div>`;
        const a = q === null ? '' : also(s);
        const lg = lines.length < 2 ? '' : `<div class="lg">${lines.map(g => `<button class="${g === f ? 'on' : ''}" data-k="${ck}" data-g="${g}" title="${esc(where(g))}"><i style="background:${g === f ? 'var(--accent)' : 'var(--border)'}"></i>${esc(sub(g))}</button>`).join('')}</div>`;
        return `<div class="tc" id="st-${esc(st.lead.g)}">
          <div><div class="tp">${esc(where(f))}</div><div class="sn">${esc(sub(f))} ${tr}</div>${head}${a ? `<div class="h2">${a}</div>` : ''}${where_}</div>
          <div>${c3(u, ck, f, [])}${lg}</div></div>`;
    }
    const cl = cs.map((c, i) => {
        const S = U.s['c:' + c], x = S.q[per], ts = topicsOf(c, lines);
        return `<div class="ci"><i style="background:${CCOL[i]}"></i><div><div class="cn1"><b>${esc(O.clabels[c])}</b><span class="cx">${x === null ? 'new' : fx(x)}</span><span class="cnn">${arts(S.nd)}</span></div>
          <div class="cin">${ts.length ? 'in ' + ts.map(g => esc(sub(g))).join(' · ') : esc(sub(O.cgroup[c]))}</div></div></div>`;
    }).join('');
    const tl = lines.map(g => { const x = U.s[g].q[per]; return `<span class="tl"><b>${esc(sub(g))}</b> ${fx(x)}</span>`; }).join('');
    const a = q === null ? '' : also(s);
    return `<div class="tc" id="st-${esc(st.lead.g)}">
      <div><div class="tp">${esc(where(f))} ${tr}</div>
        <div class="cl2">${cl}</div>
        <div class="hd">Topics, × usual in the last 4 weeks</div><div class="tls">${tl}</div>
        <div class="h2">${esc(sub(f))}: ${count(f)(s.nd)}${q !== null && q >= 1 ? since(s) : ''}${a ? ' · ' + a : ''}</div>
        ${where_}</div>
      <div>${c3(u, ck, f, cs)}</div></div>`;
}

// Lean on purpose: the database and the last 7 days.
function kpis(u) {
    const k = O.units[u].kpi, b = O.units[u].beat, t = todayIdx();
    const a7 = b.a.slice(Math.max(0, t - 6), t + 1).reduce((s, x) => s + (x || 0), 0);
    return `<div class="kpis">
      ${k.total ? `<div class="kpi"><div class="v">${k.total.toLocaleString('en')}</div><div class="t">articles in the database, to ${fmtDay(O.db_latest)}</div></div>` : ''}
      <div class="kpi"><div class="v">${a7.toLocaleString('en')}</div><div class="t">articles, last 7 days</div></div>
    </div>`;
}

const HOW = `<details class="how"><summary>How to read this</summary><ul>
  <li><b>× usual</b>: the monthly Baker index (Baker, Bloom and Davis 2016) with 2024 as the baseline T1: each source's share of articles mentioning the topic per calendar month, over its standard deviation across T1's months, averaged over the sources that published in at least half of T1's weeks, scaled so T1's months average 1×. The same shares over a week, or over the last 4 weeks, divided by the same standard deviations and scaled the same way, put weeks and the last 4 weeks on that scale: 4 weeks are the mean of their weeks. The headline is the last 4 weeks, recomputed each week. A source counts towards a topic only with ≥ 10 articles on it in T1. Regions and subregions average their countries with equal weights. "Highest since": the last complete month at or above the last 4 weeks. Under the headline, the same 4 weeks against the past 12 months (the change), and, when the monthly index has stayed at or above 1.5× its 2024 level for 2+ complete months up to last month, since when.</li>
  <li><b>Ranking</b>: how far the index sits above usual given how many articles it rests on: its n articles in the last 4 weeks against the n / q a usual 4 weeks would have at q× usual, in counting noise, (n − n/q) / √(n/q). 2× on 1,000 articles ranks above 3× on 20. A topic needs ≥ 10 articles from ≥ 3 sources in the 4 weeks and ≥ 3 on that scale, or a state.</li>
  <li><b>Grouping</b>: a topic whose articles this week mostly (≥ 50%) also mention a bigger topic that qualifies, at least 4× more often than all articles do (lift), belongs to that topic's card. Each card gathers the biggest topic its topics belong to, the topics sharing a keyword concept with it, then parents and subtopics. Cards rank by their strongest topic (the ranking above); a card's lines are sorted the same way and it opens on the first, the one that ranks it. Click a legend entry to follow another line.</li>
  <li><b>Concepts</b> lead each card: the keywords driving its topics (the concepts with the most articles above a usual week this week, at most 5), each on its own index by the same rule, with its × usual and articles in the last 4 weeks and the card topics it belongs to. Below them, the card's topics with their × usual (secondary).</li>
  <li><b>Chart</b>, × usual with 2024 as T1 on a linear scale from 0 (dashed: usual): the card's topic as a thick line, its concepts as thin ones, in three sections split by dashed lines. Left, from January 2024: in the 4-week view, 4-week blocks counted back from the last day with data (each source's standard deviation and the 1× from the blocks lying entirely inside 2024); in the calendar view, calendar months (the monthly index; the month in progress left out). Middle, the last weeks: the 4 weeks to each week, read with the blocks' standard deviations and 1×, so on a block's last day it is that block (in the calendar view the join to the months is close, not exact); it ends on the last day with data. Right: this week, empty for now. Drag the first dashed line to move where the middle section starts, on every card. Hover for the values and articles of the nearest period. A point sits on its period's last day.</li>
  <li><b>Rising / cooling this week</b>: the last week above the last 4 weeks' level and above each of the 3 weeks before it (rising), or below both (cooling).</li>
  <li><b>Where</b> (region and subregions): the countries furthest above usual on the same scale, ranked like the cards (× usual and articles together), with their × usual and articles in the last 4 weeks. Click one to open it. <b>Driven by</b>: the topic's keyword concepts with the most articles above a usual week this week.</li>
  <li><b>Themes</b>: concepts whose weekly swings move together across countries, whatever their heading, found by fixed rules (themes.py). A theme's index averages its members' indices; its counts are summed mentions (an article naming two members counts twice).</li>
  <li><b>States</b>: Bursting (weekly count ≥ 2.5× expected from its trailing 26-week share, ≥ 5 articles, Poisson p < 1e-4, in a country), Elevated (monthly index above 1.5× its 2024 level in each of the last 2+ complete months), Cooling (stopped bursting in the last 3 weeks); Pressing (on ≥ 2 of the last 3 days, ≥ 1.5× expected, ≥ 5 articles), Came back (none in the 14 days before, ≥ 10 articles in 2024), Gone quiet (bursting or elevated in the last 4 weeks, none in 7 days).</li></ul></details>`;

function render() {
    document.getElementById('window').textContent = `4 weeks to ${weekTo()}, daily to ${lastDay()} · built ${fmtDay(O.asof.slice(0, 10))}`;
    document.getElementById('window').title = asofText();
    document.getElementById('ask').textContent = 'How far above usual is each topic in the last 4 weeks?';
    const u = key(sel.value), U = O.units[u];
    if (!U) { document.getElementById('app').innerHTML = '<div class="empty">No data for this unit.</div>'; return; }
    const shown = stories(u);
    const k = 'cards:' + u, list = open.has(k) ? shown : shown.slice(0, TOP);
    document.getElementById('app').innerHTML = kpis(u)
        + (list.length ? list.map(st => storyCard(u, st)).join('') : '<div class="empty">No topic matches.</div>')
        + (shown.length > TOP ? `<button class="more" data-k="${k}">${open.has(k) ? 'Show top ' + TOP : 'Show all ' + shown.length}</button>` : '')
        + HOW;
    document.querySelectorAll('.more').forEach(b => b.onclick = () => { open.has(b.dataset.k) ? open.delete(b.dataset.k) : open.add(b.dataset.k); render(); });
    document.querySelectorAll('.lg button').forEach(b => b.onclick = () => { focus.set(b.dataset.k, b.dataset.g); render(); });
    document.querySelectorAll('.country').forEach(b => b.onclick = () => { sel.value = b.dataset.c; render(); window.scrollTo(0, 0); });
}
sel.onchange = render;
document.querySelectorAll('#view button').forEach(b => b.onclick = () => {
    view = b.dataset.v;
    document.querySelectorAll('#view button').forEach(x => x.classList.toggle('on', x === b));
    redraw();
});
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
