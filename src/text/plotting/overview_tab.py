"""The concepts dashboard's Overview tab: what is happening now, per unit.

Read ``outputs/text/<region>/overview.json`` (written by
``src/text/analysis/explorations/overview.py``). A dropdown picks the region,
a subregion or a country; "compared with" picks the baseline T1 (2024, the
past 12 or 24 months).

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
concepts. Its chart draws, on that one scale, the focused topic's weeks as
small dots, its calendar months (Baker's monthly) as large dots, the 4 weeks to
each week as a smooth line ending at the last 4 weeks (a red bar), and the
card's other topics as faint lines.

Filter toggles: Bursting, Cooling (weekly), Elevated (monthly); Pressing, Came back,
Gone quiet (the 7 UTC days ending on the newest day with articles in the
region).

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
let per = 1;
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
.filters { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; padding: 10px 0; border-top: 1px solid var(--soft); border-bottom: 1px solid var(--soft); margin-bottom: 8px; }
.tog { border: 1px solid var(--border); background: #fff; color: var(--text); border-radius: 14px; padding: 3px 10px; cursor: pointer; font-size: 12px; }
.tog b { font-variant-numeric: tabular-nums; margin-left: 4px; color: var(--muted); }
.tog.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.tog.on b { color: #fff; }
.tog:disabled { opacity: .45; cursor: default; }
.sep { width: 1px; height: 18px; background: var(--border); margin: 0 6px; }
.clear { border: 0; background: none; color: var(--accent2); cursor: pointer; font-size: 12px; font-weight: 600; }
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
.ch { position: relative; height: 120px; }
.ch svg { width: 100%; height: 100%; display: block; overflow: visible; }
.ch .ax { position: absolute; left: -2px; font-size: 9.5px; color: var(--muted); transform: translate(-100%, -50%); }
.ch .lbl { position: absolute; bottom: -14px; font-size: 9.5px; color: var(--muted); }
.ch .vd { display: none; position: absolute; bottom: -15px; transform: translateX(-50%); font-size: 10px; color: var(--text); background: var(--panel); padding: 0 4px; z-index: 1; white-space: nowrap; }
.hv .vl { stroke: #b9c4cf; stroke-dasharray: 3 3; opacity: 0; }
.hv:hover .vl { opacity: 1; }
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
.ts { position: relative; height: 170px; margin: 4px 0 18px 30px; }
.ts svg { width: 100%; height: 100%; display: block; overflow: visible; }
.ts .ya { position: absolute; left: -6px; transform: translate(-100%, -50%); font-size: 9.5px; color: var(--muted); }
.ts .xa { position: absolute; bottom: -15px; transform: translateX(-50%); font-size: 9.5px; color: var(--muted); white-space: nowrap; }
.ts .xh { display: none; position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px solid var(--muted); pointer-events: none; }
.ts .tt { display: none; position: absolute; top: 0; background: var(--panel); border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; font-size: 11px; box-shadow: 0 2px 8px rgba(0,0,0,.08); pointer-events: none; z-index: 2; white-space: nowrap; }
.ts .tt div { display: flex; align-items: center; gap: 6px; }
.ts .tt i { width: 10px; height: 3px; border-radius: 2px; }
.ts .tt span { margin-left: auto; padding-left: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }
.ts.on .xh, .ts.on .tt { display: block; }
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
  <div class="controls"><select id="unit">__UNIT_OPTIONS__</select></div>
</div>
<div class="ask" id="ask"></div>
<div class="card" id="app"></div>
<script>__SHARED_JS__
const TOP = 12, CAP = 8;
const ASK = ['2024', 'the past 12 months', 'the past 24 months'];
const COLORS = ['#169af3', '#e19d00', '#388004', '#8a3ffc', '#da1e28', '#00a3a3', '#b0517a', '#6f7d8c'];
const sel = document.getElementById('unit');
const open = new Set(), on = new Set(), focus = new Map();
const key = v => v.startsWith('region:') ? 'region' : v;
const FILTERS = [['burst', 'Bursting'], ['elev', 'Elevated'], ['cool', 'Cooling'], null, ['press', 'Pressing'], ['back', 'Came back'], ['quiet', 'Gone quiet']];
const sub = g => parts(g)[1];
const weekTo = () => fmtDay(O.week);

// The chart's time axis: the published weeks (week k of n ends n - 1 - k
// weeks before the week's end), calendar months and 4-week blocks on it.
const END = Date.parse(O.week + 'T00:00:00Z');
const weekEnd = (k, n) => END - (n - 1 - k) * 7 * DAY;
const monthStart = (k, n) => { const d = new Date(END); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - (n - 1 - k), 1); };
// Rolling: the 4 weeks to each week, the mean of their weekly values (a
// 4-week block is the mean of its weeks: one sigma and mean per source).
const roll4 = v => v.map((_, k) => k < 3 || v.slice(k - 3, k + 1).some(x => x === null) ? null : v.slice(k - 3, k + 1).reduce((a, b) => a + b, 0) / 4);
// Monotone cubic (Fritsch-Carlson) through each unbroken run of points
// (X(k), Y(v[k])): it passes through every value and never overshoots.
function smoothPath(v, X, Y) {
    let d = '';
    const runs = []; let cur = [];
    v.forEach((x, k) => { if (x === null) { if (cur.length) runs.push(cur); cur = []; } else cur.push([X(k), Y(x)]); });
    if (cur.length) runs.push(cur);
    runs.forEach(P => {
        const n = P.length, dx = [], m = [], t = [];
        for (let i = 0; i < n - 1; i++) { dx.push(P[i + 1][0] - P[i][0]); m.push((P[i + 1][1] - P[i][1]) / dx[i]); }
        for (let i = 0; i < n; i++) t.push(i === 0 ? (m[0] ?? 0) : i === n - 1 ? m[n - 2] : m[i - 1] * m[i] <= 0 ? 0 : 3 * (dx[i - 1] + dx[i]) / ((2 * dx[i] + dx[i - 1]) / m[i - 1] + (dx[i] + 2 * dx[i - 1]) / m[i]));
        d += `M${P[0][0].toFixed(1)},${P[0][1].toFixed(1)}`;
        for (let i = 0; i < n - 1; i++) {
            const h = dx[i] / 3;
            d += `C${(P[i][0] + h).toFixed(1)},${(P[i][1] + t[i] * h).toFixed(1)} ${(P[i + 1][0] - h).toFixed(1)},${(P[i + 1][1] - t[i + 1] * h).toFixed(1)} ${P[i + 1][0].toFixed(1)},${P[i + 1][1].toFixed(1)}`;
        }
    });
    return d;
}

// Concepts lead each card: the keywords driving its topics (the concepts
// with the most articles above a usual week this week, at most CONCEPTS),
// each on its own Baker index (the same rule as the topics). The text lists
// them with their x usual and the card topics they belong to; the chart draws
// them on one timeline, each as the 4 weeks to each week (a smooth line),
// with a crosshair and the week's values on hover.
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
const TS = {};
function conceptChart(u, id, cs) {
    const U = O.units[u], W = 600, H = 170;
    const v = cs.map(c => roll4(U.s['c:' + c].wh[per]));
    const nw = v[0].length, t0 = weekEnd(0, nw) - 7 * DAY, tx = t => (t - t0) / (END - t0) * W;
    const xs = v.flat().filter(x => x !== null && x > 0).map(x => x / 100);
    const lo = Math.max(.25, Math.min(.5, ...xs)), hi = Math.min(16, Math.max(2, ...xs));
    const L = x => Math.log2(Math.min(Math.max(x, lo), hi)), Y = x => H - (L(x) - Math.log2(lo)) / (Math.log2(hi) - Math.log2(lo)) * H;
    const ticks = [.25, .5, 1, 2, 4, 8, 16].filter(t => t >= lo && t <= hi);
    const wx = k => tx(weekEnd(k, nw) - 3 * DAY);
    TS[id] = {nw, cs: cs.map((c, i) => ({n: O.clabels[c], col: CCOL[i], v: v[i]})), x: k => wx(k) / W};
    const months = [];
    for (let k = 0; k < nw; k++) { const d = new Date(weekEnd(k, nw)); if (d.getUTCDate() <= 7 && d.getUTCMonth() % 3 === 0) months.push(k); }
    return `<div class="ts" data-id="${id}">
      ${ticks.map(t => `<span class="ya" style="top:${(Y(t) / H * 100).toFixed(1)}%">${t < 1 ? t : t + '×'}</span>`).join('')}
      ${months.map(k => `<span class="xa" style="left:${(wx(k) / W * 100).toFixed(1)}%">${fmtMonth(weekEnd(k, nw))}</span>`).join('')}
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        ${ticks.map(t => `<line x1="0" x2="${W}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}" stroke="var(--border)" ${t === 1 ? 'stroke-dasharray="4 3"' : 'opacity=".5"'} vector-effect="non-scaling-stroke"/>`).join('')}
        ${v.map((s, i) => `<path d="${smoothPath(s, wx, x => Y(x / 100))}" fill="none" stroke="${CCOL[i]}" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`).reverse().join('')}
      </svg><i class="xh"></i><div class="tt"></div></div>`;
}
function onTs(e) {
    const el = e.target.closest && e.target.closest('.ts');
    document.querySelectorAll('.ts.on').forEach(x => { if (x !== el) x.classList.remove('on'); });
    if (!el) return;
    const T = TS[el.dataset.id], r = el.getBoundingClientRect(), f = (e.clientX - r.left) / r.width;
    let k = 0;
    for (let j = 0; j < T.nw; j++) if (Math.abs(T.x(j) - f) < Math.abs(T.x(k) - f)) k = j;
    const xh = el.querySelector('.xh'), tt = el.querySelector('.tt');
    xh.style.left = (T.x(k) * 100) + '%';
    const rows = T.cs.map(c => [c, c.v[k]]).sort((a, b) => (b[1] ?? -1) - (a[1] ?? -1));
    tt.innerHTML = `<b>4 weeks to ${fmtDay(weekEnd(k, T.nw), {year: 'numeric'})}</b>` + rows.map(([c, x]) => `<div><i style="background:${c.col}"></i>${esc(c.n)}<span>${x === null ? '–' : fx(x / 100)}</span></div>`).join('');
    tt.style.left = T.x(k) > .6 ? '' : `calc(${T.x(k) * 100}% + 12px)`;
    tt.style.right = T.x(k) > .6 ? `calc(${(1 - T.x(k)) * 100}% + 12px)` : '';
    el.classList.add('on');
}
document.addEventListener('mousemove', onTs);

// Index view: the focused topic's weeks as dots, its calendar months (Baker's
// monthly) as larger dots and the 4 weeks to each week as a smooth line, all
// x usual on the same scale (one sigma and mean per source: the monthly
// index's, overview.py); the card's other topics as faint lines. The line
// passes through each week's 4-week value; between weeks it is a monotone
// curve (no overshoot), so every point on it read at a week is a Baker value.
function chart(u, lines, f, color) {
    const U = O.units[u], W = 600, H = 120, s = U.s[f], wk = s.wh[per], nw = wk.length;
    const t0 = weekEnd(0, nw) - 7 * DAY, span = END - t0, tx = t => (t - t0) / span * W;
    const dataEnd = Date.parse(O.data_end + 'T00:00:00Z') + DAY;
    const months = g => { const v = U.s[g].mh[per], n = v.length; return v.map((x, k) => ({x, a: monthStart(k, n), b: k === n - 1 ? Math.min(dataEnd, END + DAY) : monthStart(k + 1, n), part: k === n - 1})).filter(p => p.x !== null && p.b > t0); };
    const rl = Object.fromEntries(lines.map(g => [g, roll4(U.s[g].wh[per])]));
    const mo = months(f);
    const vals = [...wk, ...mo.map(p => p.x), ...Object.values(rl).flat()].filter(x => x !== null).map(x => x / 100);
    const max = Math.max(...vals), top = Math.max(2, Math.min(max, CAP)), Y = x => H - Math.min(x, top) / top * H;
    const wx = k => tx(weekEnd(k, nw) - 3 * DAY);
    // Monotone cubic (Fritsch-Carlson) through each unbroken run of points.
    const curve = (g, w, op) => `<path d="${smoothPath(rl[g], wx, x => Y(x / 100))}" fill="none" stroke="${color(g)}" stroke-width="${w}" opacity="${op}" vector-effect="non-scaling-stroke"/>`;
    const others = lines.filter(g => g !== f).map(g => curve(g, 1, .3)).join('');
    const r = 2.2 * W / 600;
    // Months: a larger dot at the month's middle (hollow: the month so far).
    const mdots = mo.map(p => { const x = tx((Math.max(p.a, t0) + p.b) / 2), y = Y(p.x / 100); return `<ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="${r * 1.7}" ry="${r * 1.7 * 1.5}" fill="${p.part ? 'var(--panel)' : color(f)}" stroke="${color(f)}" stroke-width="1.2" vector-effect="non-scaling-stroke"/>`; }).join('');
    const mine = curve(f, 2, 1) + mdots;
    const q = s.q[per], last = q === null ? '' : `<line x1="${tx(END - (O.days - 1) * DAY).toFixed(1)}" x2="${tx(END + DAY).toFixed(1)}" y1="${Y(q)}" y2="${Y(q)}" stroke="var(--red)" stroke-width="3.5" vector-effect="non-scaling-stroke"/>`;
    // Weeks with no article on it: a faint small dot on the axis.
    const dots = wk.map((x, k) => x === null ? '' : `<ellipse cx="${tx(weekEnd(k, nw) - 3 * DAY).toFixed(1)}" cy="${Y(x / 100).toFixed(1)}" rx="${x ? r : r * .6}" ry="${(x ? r : r * .6) * 1.5}" fill="${color(f)}" opacity="${x ? .45 : .12}"/>`).join('');
    const monthAt = t => { const p = mo.find(p => t >= p.a && t < p.b); return p ? p.x : null; };
    const text = k => {
        const t = weekEnd(k, nw) - 3 * DAY, w = wk[k];
        return [`${sub(f)}: week ${w === null ? '–' : fx(w / 100)}, month ${fx((monthAt(t) ?? NaN) / 100)}`, ...lines.map(g => `${sub(g)}: 4 weeks ${fx((rl[g][k] ?? NaN) / 100)}`)].join('\n');
    };
    const tips = wk.map((_, k) => { const x = tx(weekEnd(k, nw) - 7 * DAY), w = tx(weekEnd(k, nw)) - x; return `<g class="hv" data-t="${weekEnd(k, nw)}" data-x="${(x + w / 2) / W}"><line class="vl" x1="${x + w / 2}" x2="${x + w / 2}" y1="0" y2="${H}" vector-effect="non-scaling-stroke"/><rect x="${x}" y="0" width="${w}" height="${H}" fill="transparent"><title>Week to ${fmtDay(weekEnd(k, nw), {year: 'numeric'})}\n${text(k)}</title></rect></g>`; }).join('');
    return `<div class="ch"><span class="vd"></span>
      <span class="ax" style="top:${Y(1) / H * 120}px">1×</span><span class="ax" style="top:0">${fx(top)}${max > top ? '+' : ''}</span>
      <span class="lbl" style="left:0">${fmtDay(t0 + DAY, {year: 'numeric'})}</span><span class="lbl" style="right:0">${weekTo()}</span>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <line x1="0" x2="${W}" y1="${Y(1)}" y2="${Y(1)}" stroke="var(--border)" stroke-dasharray="4 3" vector-effect="non-scaling-stroke"/>
        ${others}${dots}${mine}${last}${tips}
      </svg></div>`;
}
function onHover(e) {
    const g = e.target.closest('.hv'), ch = e.target.closest('.ch');
    if (!g || !ch) return;
    const vd = ch.querySelector('.vd');
    vd.textContent = fmtDay(+g.dataset.t, {year: 'numeric'});
    vd.style.left = (+g.dataset.x * 100) + '%';
    vd.style.display = 'block';
}
document.addEventListener('mouseover', onHover);
document.addEventListener('mouseout', e => { const ch = e.target.closest && e.target.closest('.ch'); if (ch && !ch.contains(e.relatedTarget)) ch.querySelector('.vd').style.display = 'none'; });

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

// The other comparison, from the same index: the last 4 weeks against 2024
// (level) when the past months are picked, against the past 12 months
// (change) when 2024 is; and how long the monthly index has run at >= 1.5x
// its 2024 level, counting back from the last complete month (>= 2 months).
function also(s) {
    const o = per === 0 ? 1 : 0, x = s.q[o];
    const vs = x === null ? '' : `${fx(x)} ${o === 0 ? 'its 2024 level' : 'the past 12 months'}`;
    const m = s.mh[0], n = m.length;
    let k = 0;
    while (k < n - 1 && m[n - 2 - k] !== null && m[n - 2 - k] >= 150) k++;
    const run = k < 2 ? '' : `above 1.5× its 2024 level since ${fmtMonth(monthStart(n - 1 - k, n))}`;
    return [vs, run].filter(Boolean).join(' · ');
}

function storyCard(u, st) {
    const U = O.units[u], ck = u + st.lead.g;
    const lines = st.lines.slice(0, LINES).map(x => x.g);
    const f = lines.includes(focus.get(ck)) ? focus.get(ck) : lines[0];
    const color = g => g === lines[0] ? 'var(--accent)' : COLORS[(lines.indexOf(g) - 1) % COLORS.length];
    const s = U.s[f], q = s.q[per];
    const tr = s.tr === 1 ? '<span class="tr up">rising this week</span>' : s.tr === -1 ? '<span class="tr dn">cooling this week</span>' : '';
    const w = (s.w || [])[per] || [];
    const where_ = w.length ? `<div class="hd">Where</div>${w.map(([c, x, n]) => `<button class="chip country" data-c="${c}" title="${count(f)(n)} in the 4 weeks to ${weekTo()}">${esc(name(c))} ${fx(x)} · ${count(f)(n)}</button>`).join('')}` : '';
    const cs = cardConcepts(u, lines).filter(c => U.s['c:' + c].wh);
    if (!cs.length) {  // no driving concepts: the topic view
        const head = q === null ? '<div class="hl">No usual level to compare with</div>'
            : `<div class="hl">${fx(q)} <span>usual, last 4 weeks · ${count(f)(s.nd)}${q >= 1 ? since(s) : ''}</span></div>`;
        const a = q === null ? '' : also(s);
        const lg = lines.length < 2 ? '' : `<div class="lg">${lines.map(g => `<button class="${g === f ? 'on' : ''}" data-k="${ck}" data-g="${g}" title="${esc(where(g))}"><i style="background:${color(g)}"></i>${esc(sub(g))}</button>`).join('')}</div>`;
        return `<div class="tc" id="st-${esc(st.lead.g)}">
          <div><div class="tp">${esc(where(f))}</div><div class="sn">${esc(sub(f))} ${tr}</div>${head}${a ? `<div class="h2">${a}</div>` : ''}${where_}</div>
          <div>${chart(u, lines, f, color)}${lg}</div></div>`;
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
      <div>${conceptChart(u, ck, cs)}</div></div>`;
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

function filters(list) {
    const cnt = tag => list.filter(x => x.tags.has(tag)).length;
    return `<div class="filters">${FILTERS.map(f => !f ? '<span class="sep"></span>' :
        `<button class="tog ${on.has(f[0]) ? 'on' : ''}" data-t="${f[0]}" ${cnt(f[0]) ? '' : 'disabled'}>${f[1]}<b>${cnt(f[0])}</b></button>`).join('')}
      ${on.size ? '<button class="clear">Show all</button>' : ''}</div>`;
}

const HOW = `<details class="how"><summary>How to read this</summary><ul>
  <li><b>× usual</b>: the monthly Baker index (Baker, Bloom and Davis 2016) with the "compared with" period as the baseline T1: each source's share of articles mentioning the topic per calendar month, over its standard deviation across T1's months, averaged over the sources that published in at least half of T1's weeks, scaled so T1's months average 1×. The same shares over a week, or over the last 4 weeks, divided by the same standard deviations and scaled the same way, put weeks and the last 4 weeks on that scale: 4 weeks are the mean of their weeks. The headline is the last 4 weeks, recomputed each week. A source counts towards a topic only with ≥ 10 articles on it in T1. Regions and subregions average their countries with equal weights. "Highest since": the last complete month at or above the last 4 weeks. Under the headline, the same 4 weeks against the other baseline (2024, the level; or the past 12 months, the change), and, when the monthly index has stayed at or above 1.5× its 2024 level for 2+ complete months up to last month, since when.</li>
  <li><b>Ranking</b>: how far the index sits above usual given how many articles it rests on: its n articles in the last 4 weeks against the n / q a usual 4 weeks would have at q× usual, in counting noise, (n − n/q) / √(n/q). 2× on 1,000 articles ranks above 3× on 20. A topic needs ≥ 10 articles from ≥ 3 sources in the 4 weeks and ≥ 3 on that scale, or a state.</li>
  <li><b>Grouping</b>: a topic whose articles this week mostly (≥ 50%) also mention a bigger topic that qualifies, at least 4× more often than all articles do (lift), belongs to that topic's card. Each card gathers the biggest topic its topics belong to, the topics sharing a keyword concept with it, then parents and subtopics. Cards rank by their strongest topic (the ranking above); a card's lines are sorted the same way and it opens on the first, the one that ranks it. Click a legend entry to follow another line.</li>
  <li><b>Concepts</b> lead each card: the keywords driving its topics (the concepts with the most articles above a usual week this week, at most 5), each on its own index by the same rule, with its × usual and articles in the last 4 weeks and the card topics it belongs to. The chart draws them on one timeline (log scale, dashed: usual), each as the 4 weeks to each week, a smooth line through the weekly values; hover for a week's values. Below them, the card's topics with their × usual (secondary).</li>
  <li><b>Chart</b> (cards without driving concepts), two years on one × usual scale: small dots = the focused topic's weeks (faint on the axis: no article that week); large dots = its calendar months (Baker's monthly; hollow: the month so far); line = the 4 weeks to each week, drawn as a smooth curve through the weekly values; red = the last 4 weeks (the headline, where the line ends); faint lines = the card's other topics; dashed line = usual.</li>
  <li><b>Rising / cooling this week</b>: the last week above the last 4 weeks' level and above each of the 3 weeks before it (rising), or below both (cooling).</li>
  <li><b>Where</b> (region and subregions): the countries furthest above usual on the same scale, ranked like the cards (× usual and articles together), with their × usual and articles in the last 4 weeks. Click one to open it. <b>Driven by</b>: the topic's keyword concepts with the most articles above a usual week this week.</li>
  <li><b>Themes</b>: concepts whose weekly swings move together across countries, whatever their heading, found by fixed rules (themes.py). A theme's index averages its members' indices; its counts are summed mentions (an article naming two members counts twice).</li>
  <li><b>Toggles</b>: Bursting (weekly count ≥ 2.5× expected from its trailing 26-week share, ≥ 5 articles, Poisson p < 1e-4, in a country), Elevated (monthly index above 1.5× its 2024 level in each of the last 2+ complete months), Cooling (stopped bursting in the last 3 weeks); Pressing (on ≥ 2 of the last 3 days, ≥ 1.5× expected, ≥ 5 articles), Came back (none in the 14 days before, ≥ 10 articles in 2024), Gone quiet (bursting or elevated in the last 4 weeks, none in 7 days). A card shows when one of its topics matches any picked.</li></ul></details>`;

function render() {
    document.getElementById('window').textContent = `4 weeks to ${weekTo()}, daily to ${lastDay()} · built ${fmtDay(O.asof.slice(0, 10))}`;
    document.getElementById('window').title = asofText();
    document.getElementById('ask').innerHTML = `How far above usual is each topic in the last 4 weeks, compared with
      <span class="seg">${ASK.map((t, i) => `<button data-p="${i}" class="${i === per ? 'on' : ''}">${t}</button>`).join('')}</span>?`;
    const u = key(sel.value), U = O.units[u];
    if (!U) { document.getElementById('app').innerHTML = '<div class="empty">No data for this unit.</div>'; return; }
    const all = stories(u);
    const shown = on.size ? all.filter(x => [...on].some(t => x.tags.has(t))) : all;
    const k = 'cards:' + u, list = open.has(k) ? shown : shown.slice(0, TOP);
    document.getElementById('app').innerHTML = kpis(u) + filters(shown)
        + (list.length ? list.map(st => storyCard(u, st)).join('') : '<div class="empty">No topic matches.</div>')
        + (shown.length > TOP ? `<button class="more" data-k="${k}">${open.has(k) ? 'Show top ' + TOP : 'Show all ' + shown.length}</button>` : '')
        + HOW;
    document.querySelectorAll('.ask button[data-p]').forEach(b => b.onclick = () => { per = +b.dataset.p; render(); });
    document.querySelectorAll('.tog[data-t]').forEach(b => b.onclick = () => { on.has(b.dataset.t) ? on.delete(b.dataset.t) : on.add(b.dataset.t); render(); });
    document.querySelectorAll('.clear').forEach(b => b.onclick = () => { on.clear(); render(); });
    document.querySelectorAll('.more').forEach(b => b.onclick = () => { open.has(b.dataset.k) ? open.delete(b.dataset.k) : open.add(b.dataset.k); render(); });
    document.querySelectorAll('.lg button').forEach(b => b.onclick = () => { focus.set(b.dataset.k, b.dataset.g); render(); });
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
