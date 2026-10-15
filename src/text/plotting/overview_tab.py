"""The concepts dashboard's Overview tab: what is happening now, per unit.

Read ``outputs/text/<region>/overview.json`` (written by
``src/text/analysis/explorations/overview.py``). A dropdown picks the region,
a subregion or a country; the baseline T1 is 2024.

Per unit: two KPIs (articles in the database, last 7 days), the ranked topic
cards, then the theme cards. Every topic, subtopic and theme has a weekly
and a monthly Baker index, each with 2024 = 1x (sources weighted by their
articles, overview.py). Its headline is the weekly index's mean over the last
4 complete weeks (``q4``, x its 2024 level), and it ranks by how far that
sits above 1x in counting noise, (n - n/q) / sqrt(n/q) for its n articles in
those weeks. A topic whose articles mostly also mention a bigger topic
(``co``: same articles, overview.py) belongs to that topic's card; going down
the ranking, each card is led by the biggest topic its first topic belongs
to and pulls in the topics belonging there, those sharing a concept with it,
then the parents and subtopics of everything in the card. A card ranks by
and shows its strongest topic. Themes are ranked the same way in their own
section.

A card: the topic, its x and articles; at most two badges ("highest since",
rising or cooling) and "part of" a theme; the concepts driving its topics
(>= 10 articles in the last 4 weeks and a 2024 level) with their x; the
countries furthest above their 2024 level (region and subregions); and one
chart, the topic thick and its concepts thin, in three sections: the
trailing 3-month mean of the monthly index to a draggable line, the trailing
4-, 3- or 2-week mean of the weekly index (page buttons) from there to the
last complete week, and an empty "this week" band. Each section has a fixed
density (months narrow, weeks wide), so dragging the line trades months for
weeks, on every card. A topic with no 2024 level gets a note, not a chart.

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
.t1 { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.t1 .sn { font-weight: 700; font-size: 15px; }
.t1 .hx { font-size: 13px; font-weight: 700; color: #fff; background: var(--accent); border-radius: 10px; padding: 1px 8px; font-variant-numeric: tabular-nums; }
.bds { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }
.bd { font-size: 10.5px; font-weight: 600; border-radius: 8px; padding: 1px 7px; white-space: nowrap; background: var(--soft); color: var(--muted); }
.bd.up { background: #fde8e9; color: var(--red); }
.bd.th { background: #e6f3fe; color: var(--accent); }
.hd { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .04em; margin-top: 10px; }
.chip { display: inline-block; border: 1px solid var(--border); background: #fff; color: var(--text); border-radius: 12px; padding: 1px 8px; margin: 3px 3px 0 0; font-size: 11px; cursor: pointer; font-variant-numeric: tabular-nums; }
.chip:hover { border-color: var(--accent2); }
.ask { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 14px; margin-bottom: 12px; }
.lg { display: grid; gap: 3px; margin-top: 10px; font-size: 12px; }
.lg span { display: flex; align-items: center; gap: 6px; }
.lg i { display: inline-block; width: 14px; height: 3px; border-radius: 2px; flex: none; }
.sh { font-weight: 700; font-size: 15px; margin: 22px 0 2px; padding-top: 14px; border-top: 2px solid var(--border); }
.nolevel { color: var(--muted); font-size: 12px; padding: 8px 0; }
.c3 { margin: 0 0 18px 30px; position: relative; }
.c3 .pl { position: relative; height: 170px; touch-action: none; }
.c3 svg { width: 100%; height: 100%; display: block; overflow: visible; }
.c3 .ya { position: absolute; left: -6px; transform: translate(-100%, -50%); font-size: 9.5px; color: var(--muted); }
.c3 .xa { position: absolute; bottom: -15px; transform: translateX(-50%); font-size: 9.5px; color: var(--muted); white-space: nowrap; }
.c3 .xa.r { transform: translateX(calc(-100% - 3px)); }
.c3 .d1 { position: absolute; top: 0; bottom: 0; width: 12px; transform: translateX(-50%); cursor: ew-resize; z-index: 1; }
.c3 .xh { display: none; position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px solid var(--muted); pointer-events: none; }
.c3 .xd { display: none; position: absolute; bottom: -16px; transform: translateX(-50%); font-size: 10px; font-weight: 600; color: var(--text); background: var(--soft); border-radius: 3px; padding: 0 4px; white-space: nowrap; pointer-events: none; z-index: 1; }
.c3 .tt { display: none; position: absolute; bottom: calc(100% + 2px); background: var(--panel); border: 1px solid var(--border); border-radius: 6px; padding: 3px 6px; font-size: 11px; line-height: 15px; box-shadow: 0 2px 8px rgba(0,0,0,.08); pointer-events: none; z-index: 3; white-space: nowrap; }
.c3 .tt table { border-collapse: collapse; }
.c3 .tt td { padding: 0 4px; }
.c3 .tt i { display: block; width: 12px; border-radius: 2px; }
.c3 .tt .x { text-align: right; font-size: 11px; }
.c3.on .xh, .c3.on .xd, .c3.on .tt { display: block; }
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
  <div class="controls"><span class="seg" id="ma"><span>Weekly mean</span><button data-k="4" class="on">4w</button><button data-k="3">3w</button><button data-k="2">2w</button></span><select id="unit">__UNIT_OPTIONS__</select></div>
</div>
<div class="ask" id="ask"></div>
<div class="card" id="app"></div>
<script>__SHARED_JS__
const TOP = 12;
const sel = document.getElementById('unit');
const open = new Set();
const key = v => v.startsWith('region:') ? 'region' : v;
const sub = g => parts(g)[1];
const weekTo = () => fmtDay(O.week);

// Calendar months counted back from the week's end ("highest since").
const END = Date.parse(O.week + 'T00:00:00Z');
const monthStart = (k, n) => { const d = new Date(END); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - (n - 1 - k), 1); };

// Trailing mean of the non-null values in the n points to j (null: none),
// and the sum of the counts.
const tmean = (v, j, n) => { let s = 0, c = 0; for (let i = Math.max(0, j - n + 1); i <= j; i++) if (v[i] !== null) { s += v[i]; c++; } return c ? s / c : null; };
const tsum = (v, j, n) => { let s = 0; for (let i = Math.max(0, j - n + 1); i <= j; i++) s += v[i] || 0; return s; };
// x its 2024 level: the weekly index's mean over the last 4 weeks, the
// chart's last weekly point at 4w (headline, ranking, concepts).
const q4 = s => { const m = s && s.wk ? tmean(s.wk, s.wk.length - 1, 4) : null; return m === null ? null : m / 100; };

// Concepts in each card's legend and chart: the keywords driving its topics
// (the concepts with the most articles above a usual week this week, at most
// CONCEPTS) with >= C_MIN articles in the last 4 weeks and a 2024 level.
const CONCEPTS = 5, C_MIN = 10, CCOL = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];
function cardConcepts(u, lines) {
    const U = O.units[u], S = c => U.s['c:' + c], cs = [];
    for (const g of lines) for (const [c] of U.dc[g] || []) if (!cs.includes(c) && S(c) && S(c).nd >= C_MIN && q4(S(c)) !== null) cs.push(c);
    return cs.sort((a, b) => q4(S(b)) - q4(S(a))).slice(0, CONCEPTS);
}

// The chart, x the 2024 level, in three sections split by two dashed lines:
// (1) to line 1, the trailing 3-month mean of the monthly index (complete
// months); (2) from line 1 to t0 (the last complete week), the trailing
// mean of the weekly index over K weeks (page buttons); (3) this week, empty
// for now. Each section has a fixed density (months narrow, weeks wide: 2
// years and 12 weeks at the default), so dragging line 1 moves the date it
// stands for, on every card. A point sits on its period's last day.
const T0 = END, WK = 7 * DAY, W0 = Date.parse(O.w0 + 'T00:00:00Z');
const [MY, MM] = O.m0.split('-').map(Number);
const monthEnd = j => Date.UTC(MY, MM + j, 1) - DAY;
const CW = 600, CHH = 170, XB = .92 * CW, XA0 = .46 * CW;
const K1 = XA0 / (730.5 * DAY), K2 = (XB - XA0) / (12 * WK);  // units per ms
const XA_MIN = 92 * DAY * K1, XA_MAX = XB - 4 * WK * K2;
let xa = XA0, K = 4;
const CHARTS = {};
function xmap() {
    const L = T0 - (XB - xa) / K2;
    return {L, a: xa, b: XB, X: t => t >= L ? xa + (t - L) * K2 : xa - (L - t) * K1,
        T: x => x >= xa ? L + (x - xa) / K2 : L - (xa - x) / K1};
}
// A line's points per section: {t, x (x 100), n (articles in the window)}.
function pts(s, M) {
    const one = s.mo.map((_, j) => ({t: monthEnd(j), x: j < 2 ? null : tmean(s.mo, j, 3), n: tsum(s.nm, j, 3)}));
    const two = s.wk.map((_, j) => ({t: W0 + j * WK, x: j < K - 1 ? null : tmean(s.wk, j, K), n: tsum(s.nw, j, K)}));
    return [one.filter(p => p.t <= M.L && M.X(p.t) >= 0), two.filter(p => p.t >= M.L)];
}
function c3(u, id, f, cs) {
    const U = O.units[u];
    CHARTS[id] = [{s: U.s[f], n: sub(f), col: 'var(--accent)', w: 2.6, cnt: count(f)},
        ...cs.map((c, i) => ({s: U.s['c:' + c], n: O.clabels[c], col: CCOL[i], w: 1.4, cnt: arts}))];
    // The hover table's rows fit in the strip reserved above the plot.
    return `<div class="c3" data-id="${esc(id)}" style="padding-top:${CHARTS[id].length * 15 + 12}px"><div class="pl">${plot(id)}</div></div>`;
}
function plot(id) {
    const C = CHARTS[id], M = xmap(), P = C.map(l => pts(l.s, M));
    const xs = P.flat(2).map(p => p.x).filter(x => x !== null);
    const max = Math.max(100, ...xs) / 100;
    const step = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000].find(v => v >= max / 5) || Math.ceil(max / 5);
    const top = Math.max(2, Math.ceil(max / step) * step), Y = x => CHH - x / top * CHH;
    const grid = [];
    for (let v = step; v <= top; v += step) grid.push(v);
    if (!grid.includes(1)) grid.push(1);
    const path = ps => { let d = '', pen = false; for (const p of ps) { if (p.x === null) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${M.X(p.t).toFixed(1)},${Y(p.x / 100).toFixed(1)}`; pen = true; } return d; };
    const pc = x => (x / CW * 100).toFixed(2) + '%';
    const xl = [], t1 = M.T(0);
    for (let y = new Date(t1).getUTCFullYear(), k = 0; ; k++) {  // section 1: quarters
        const a = Date.UTC(y, 3 * k, 1), b = Date.UTC(y, 3 * k + 3, 1);
        if (b > M.L) break;
        if (a >= t1) xl.push([(M.X(a) + M.X(b)) / 2, `Q${k % 4 + 1} '${String((y + Math.floor(k / 4)) % 100).padStart(2, '0')}`]);
    }
    // Section 2: every 4 weeks back from t0.
    for (let t = T0 - 4 * WK; t >= M.L; t -= 4 * WK) if (M.X(t) - M.a >= 18) xl.push([M.X(t), fmtDay(t)]);
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
// and its values in a table in the strip above the plot.
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
    const sec = x <= M.a ? 0 : 1, P = C.map(l => pts(l.s, M)[sec]), t = M.T(x);
    if (!P[0].length) { tt.style.visibility = 'hidden'; return; }
    let k = 0;
    P[0].forEach((p, j) => { if (Math.abs(p.t - t) < Math.abs(P[0][k].t - t)) k = j; });
    const p0 = P[0][k];
    xd.textContent = sec === 0 ? `3 months to ${fmtMonth(p0.t)}` : `${K} weeks to ${fmtDay(p0.t, {year: 'numeric'})}`;
    xd.style.left = M.X(p0.t) / CW * 100 + '%';
    tt.innerHTML = '<table>' + C.map((l, i) => { const p = P[i][k]; return `<tr><td><i style="background:${l.col};height:${l.w > 2 ? 4 : 2}px"></i></td><td>${esc(l.n)}</td><td class="x">${p.x === null ? '–' : fx(p.x / 100)}</td><td class="n">${l.cnt(p.n)}</td></tr>`; }).join('') + '</table>';
    tt.style.visibility = '';
    const w = tt.offsetWidth, cx = x / CW * r.width;
    tt.style.left = Math.min(Math.max(cx - w / 2, 0), Math.max(0, r.width - w)) + 'px';
}
let drag = null, frame = 0;
document.addEventListener('mousemove', onMove);
document.documentElement.addEventListener('mouseleave', () => document.querySelectorAll('.c3.on').forEach(x => x.classList.remove('on')));
document.addEventListener('pointerdown', e => {
    const h = e.target.closest && e.target.closest('.d1');
    if (!h) return;
    drag = {r: h.parentElement.getBoundingClientRect()};
    document.querySelectorAll('.c3.on').forEach(x => x.classList.remove('on'));
    e.preventDefault();
});
document.addEventListener('pointermove', e => {
    if (!drag) return;
    xa = Math.min(Math.max((e.clientX - drag.r.left) / drag.r.width * CW, XA_MIN), XA_MAX);
    if (!frame) frame = requestAnimationFrame(() => { frame = 0; redraw(); });
});
document.addEventListener('pointerup', () => { drag = null; });

// Stories: every topic and subtopic ranked by how far its last 4 weeks
// (q4, x its 2024 level) sit above that level in counting noise: its n
// articles against the n / q a 2024-like 4 weeks would have,
// (n - n/q) / sqrt(n/q). A topic qualifies with >= N_MIN articles from >=
// MIN_SOURCES sources in those days and either >= Z_MIN or a state. Themes
// are ranked the same way in their own section.
// Grouping: a topic's home is the topic >= Z_MIN, among the bigger ones
// most of its articles also mention (U.co), with the highest lift; its
// root follows homes up. Going down the ranking, a topic not yet placed
// opens a story led by its root, which pulls in every topic with that root,
// those sharing a concept with the root or the first topic (a group's and
// its subgroups' concepts), then the parents and subtopics of everything in
// the story. A story ranks by its first topic (its strongest) and its card
// shows that topic, with the concepts of all its topics.
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
        const s = U.s[g], r = rows.get(g), bt = U.beat.g[g] ? beat(u, g) : null, tags = new Set(), q = q4(s);
        if (r && r.b && r.b[0] !== 'fade') tags.add('burst');
        if (r && r.b && r.b[0] === 'fade') tags.add('cool');
        if (r && r.p) tags.add('elev');
        if (g.startsWith('t:') && s.b) tags.add('burst');
        if (bt && BEAT_STATES[bt.state]) tags.add(bt.state);
        return {g, n: s.nd, ns: s.ns, q: q === null ? 0 : q, z: above(q, s.nd), tags, cs: conceptsOf(g)};
    }).filter(t => t.n >= N_MIN && t.ns >= MIN_SOURCES && (t.z >= Z_MIN || t.tags.size)).sort((a, b) => b.z - a.z);
}

const kin = (a, b) => parentOf[a.g] === b.g || parentOf[b.g] === a.g;
const shares = (a, b) => [...a.cs].some(c => b.cs.has(c));

function stories(u) {
    const live = topics(u).filter(t => !t.g.startsWith('t:'));
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
        lines.sort((a, b) => b.z - a.z);  // the card shows the line that ranks it
        out.push({lines, late: [...tags].every(x => x === 'cool' || x === 'quiet')});
    }
    return out.sort((a, b) => a.late - b.late);  // stable: the ranking otherwise
}

// A topic's place (the title's tooltip): theme headings, or heading and parent.
function where(g) {
    const t = themeOf(g);
    if (t) return 'Theme · ' + t.headings.join(' · ');
    return parts(g)[0] + (parentOf[g] ? ' · in ' + sub(parentOf[g]) : '');
}

// "Highest since": the latest earlier 4 weeks at or above the last 4 weeks,
// when before last month (null: none since 2015).
function since(s) {
    if (s.hs === null) return 'highest since 2015';
    const t = Date.parse(s.hs + '-01T00:00:00Z');
    return t < monthStart(0, 2) ? `highest since ${fmtMonth(t)}` : '';
}
// The theme sharing the most concepts with a topic.
function partOf(g) {
    const cs = conceptsOf(g);
    let best = null, nb = 0;
    O.themes.forEach(t => { const n = t.members.filter(c => cs.has(c)).length; if (n > nb) { best = t; nb = n; } });
    return best && best.name;
}

function card(u, f, lines) {
    const U = O.units[u], s = U.s[f], q = q4(s), cnt = count(f), id = u + '|' + f;
    const hs = q !== null && q >= 1 ? since(s) : '';
    const tr = s.tr === 1 ? 'rising this week' : s.tr === -1 ? 'cooling this week' : '';
    const th = f.startsWith('t:') ? null : partOf(f);
    const bd = (hs ? `<span class="bd">${hs}</span>` : '') + (tr ? `<span class="bd${s.tr === 1 ? ' up' : ''}">${tr}</span>` : '')
        + (th ? `<span class="bd th">part of: ${esc(th)}</span>` : '');
    const cs = cardConcepts(u, lines);
    const lg = cs.length ? `<div class="lg">${cs.map((c, i) => `<span><i style="background:${CCOL[i]}"></i>${esc(O.clabels[c])} <b class="x">${fx(q4(U.s['c:' + c]))}</b></span>`).join('')}</div>` : '';
    const w = s.w || [];
    const wh = w.length ? `<div class="hd">Where</div>${w.map(([c, x, n]) => `<button class="chip country" data-c="${c}" title="${cnt(n)} in the 4 weeks to ${weekTo()}">${esc(name(c))} ${fx(x)}</button>`).join('')}` : '';
    const level = [...s.wk, ...s.mo].some(x => x !== null);
    return `<div class="tc">
      <div><div class="t1"><span class="sn" title="${esc(where(f))}">${esc(sub(f))}</span>${q === null ? '' : `<span class="hx" title="× its 2024 level, last 4 weeks">${fx(q)}</span>`}<span class="n">${cnt(s.nd)}</span></div>
        ${bd ? `<div class="bds">${bd}</div>` : ''}${lg}${wh}</div>
      <div>${level ? c3(u, id, f, cs) : '<div class="nolevel">No 2024 level</div>'}</div></div>`;
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
  <li><b>× its 2024 level</b>: the Baker index (Baker, Bloom and Davis 2016), weekly and monthly, each its own index with 2024 as the baseline. Per source, the share of its articles in the week (or month) mentioning the topic, over that share's standard deviation across 2024's weeks (or months); averaged over the sources that published in at least half of 2024's weeks, each weighted by its share of the period's articles among the sources with articles then; scaled so 2024 averages 1×. A source counts towards a topic only with ≥ 10 articles on it in 2024. Regions and subregions: each country's index over its standard deviation across 2024, averaged with equal weights, scaled the same way. The headline is the weekly index's mean over the last 4 complete weeks (the chart's last weekly point at 4w, whatever the buttons). "Highest since": the latest earlier 4 weeks at or above it.</li>
  <li><b>Ranking</b>: how far a topic sits above its 2024 level given how many articles it rests on: its n articles in the last 4 weeks against the n / q a 2024-like 4 weeks would have at q×, in counting noise, (n − n/q) / √(n/q). 2× on 1,000 articles ranks above 3× on 20. A topic needs ≥ 10 articles from ≥ 3 sources in the 4 weeks and ≥ 3 on that scale, or a state.</li>
  <li><b>Grouping</b>: a topic whose articles this week mostly (≥ 50%) also mention a bigger topic that qualifies, at least 4× more often than all articles do (lift), belongs to that topic's card. Each card gathers the biggest topic its topics belong to, the topics sharing a keyword concept with it, then parents and subtopics, and shows the one that ranks it highest.</li>
  <li><b>Concepts</b> (the card's legend and thin lines): the keywords driving the card's topics (the concepts with the most articles above a usual week this week, at most 5) with ≥ 10 articles in the last 4 weeks and a 2024 level, each with its × on the same rule.</li>
  <li><b>Chart</b>, × the 2024 level on a linear scale from 0 (dashed: 1×): the card's topic thick, its concepts thin, in three sections split by dashed lines. Left: the trailing 3-month mean of the monthly index (complete months). Middle: the trailing mean of the weekly index over 4, 3 or 2 weeks (the buttons), to the last complete week. Right: this week, empty for now. Months are drawn narrow and weeks wide; drag the first dashed line to trade months for weeks, on every card. Hover for the values and articles of the nearest point; a point sits on its period's last day.</li>
  <li><b>Rising / cooling this week</b>: the last week's weekly index above its 4-week mean and above each of the 3 weeks before (rising), or below both (cooling). <b>Part of</b>: the theme sharing the most keyword concepts with the topic.</li>
  <li><b>Where</b> (region and subregions): the countries furthest above their 2024 level, ranked like the cards (× and articles together), with ≥ 5 articles in the last 4 weeks; hover for the articles. Click one to open it.</li>
  <li><b>Themes</b> (their own section): concepts whose weekly swings move together across countries, whatever their heading, found by fixed rules (themes.py). A theme's index averages its members' indices, each over its 2024 mean; its counts are summed mentions (an article naming two members counts twice), so they read "mentions".</li>
  <li><b>States</b>: Bursting (weekly count ≥ 2.5× expected from its trailing 26-week share, ≥ 5 articles, Poisson p < 1e-4, in a country), Elevated (monthly index above 1.5× its 2024 level in each of the last 2+ complete months), Cooling (stopped bursting in the last 3 weeks); Pressing (on ≥ 2 of the last 3 days, ≥ 1.5× expected, ≥ 5 articles), Came back (none in the 14 days before, ≥ 10 articles in 2024), Gone quiet (bursting or elevated in the last 4 weeks, none in 7 days).</li></ul></details>`;

function render() {
    document.getElementById('window').textContent = `4 weeks to ${weekTo()}, daily to ${lastDay()} · built ${fmtDay(O.asof.slice(0, 10))}`;
    document.getElementById('window').title = asofText();
    document.getElementById('ask').textContent = 'Which topics are furthest above their 2024 level in the last 4 weeks, by how much they are discussed?';
    const u = key(sel.value), U = O.units[u];
    if (!U) { document.getElementById('app').innerHTML = '<div class="empty">No data for this unit.</div>'; return; }
    for (const id in CHARTS) delete CHARTS[id];
    const shown = stories(u), th = topics(u).filter(t => t.g.startsWith('t:'));
    const k = 'cards:' + u, list = open.has(k) ? shown : shown.slice(0, TOP);
    document.getElementById('app').innerHTML = kpis(u)
        + (list.length ? list.map(st => card(u, st.lines[0].g, st.lines.slice(0, LINES).map(x => x.g))).join('') : '<div class="empty">No topic matches.</div>')
        + (shown.length > TOP ? `<button class="more" data-k="${k}">${open.has(k) ? 'Show top ' + TOP : 'Show all ' + shown.length}</button>` : '')
        + (th.length ? '<div class="sh">Themes</div>' + th.map(t => card(u, t.g, [t.g])).join('') : '')
        + HOW;
    document.querySelectorAll('.more').forEach(b => b.onclick = () => { open.has(b.dataset.k) ? open.delete(b.dataset.k) : open.add(b.dataset.k); render(); });
    document.querySelectorAll('.country').forEach(b => b.onclick = () => { sel.value = b.dataset.c; render(); window.scrollTo(0, 0); });
}
sel.onchange = render;
document.querySelectorAll('#ma button').forEach(b => b.onclick = () => {
    K = +b.dataset.k;
    document.querySelectorAll('#ma button').forEach(x => x.classList.toggle('on', x === b));
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
