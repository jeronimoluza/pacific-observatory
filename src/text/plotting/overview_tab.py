"""The concepts dashboard's Overview and Country tabs: subtopic bursts this week.

Read ``outputs/text/<region>/overview.json`` (written by
``src/text/analysis/explorations/overview.py``). Overview: a region card (KPIs,
top bursting subtopics, one row per subregion with subtopics shared by its
countries), then per subregion a table of its countries. Country (a stub for
now): every bursting and fading subtopic of the unit picked. Rows rank by
articles above a usual week (N - N / ratio); a "Compare with" switch picks the
usual week (2024, past year, 26 or 8 weeks). Each tab is a self-contained page
that the host embeds as an iframe ``srcdoc``.

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
.lab small { color: var(--muted); font-weight: 400; }
.lab .cx { display: block; color: var(--muted); font-size: 11px; }
.x { font-weight: 700; font-variant-numeric: tabular-nums; }
.n { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; margin-left: 3px; }
.badge { display: inline-block; font-size: 10.5px; font-weight: 600; border-radius: 4px; padding: 1px 6px; white-space: nowrap; }
.b-new { background: var(--red); color: #fff; }
.b-rise { background: #e8f3df; color: var(--green); }
.b-peak { background: #fdf3d9; color: #8a5f00; }
.b-wk { background: var(--soft); color: var(--accent); }
.b-fade { background: #f0f2f4; color: var(--muted); }
.b-pers { background: #fde8e9; color: var(--red); }
.badges { display: inline-flex; gap: 4px; flex-wrap: wrap; }
table.rows { width: 100%; border-collapse: collapse; }
table.rows td { padding: 5px 6px; border-top: 1px solid var(--soft); vertical-align: top; }
table.rows td.num { text-align: right; white-space: nowrap; line-height: 1.3; }
table.rows td.num .n { display: block; margin: 0; }
table.rows tr.fade td { opacity: .55; }
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
const ratio = r => r[per] === null ? '–' : (r[per] >= 10 ? Math.round(r[per]) : r[per].toFixed(1)) + '× usual';
// No ratio: either no source with 2024 data covers it (u, ranked last) or it was absent in the period (all extra).
const score = r => r.u ? 0 : r.r[per] === null || r.r[per] <= 0 ? r.n : r.n - r.n / r.r[per];
const arts = n => `${n.toLocaleString('en')} article${n === 1 ? '' : 's'}`;
const byScore = rows => [...rows].sort((a, b) => score(b) - score(a));
const ord = k => k + (k % 100 >= 11 && k % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][k % 10] || 'th');
function badge(r) {
    const out = [];
    if (r.b) {
        const [k, v] = r.b;
        const t = k === 'new' ? 'NEW' : k === 'rise' ? `${ord(v)} wk rising` : k === 'peak' ? `Peaked ${v} wk ago`
            : k === 'wk' ? `${ord(v)} wk` : 'Fading';
        out.push(`<span class="badge b-${k}">${t}</span>`);
    }
    if (r.p) out.push(`<span class="badge b-pers">↑ ${r.p} wks above 2024</span>`);
    return `<span class="badges">${out.join('')}</span>`;
}
const fmtDay = d => new Date(d + 'T00:00:00Z').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC'});
const weekStart = d => { const t = new Date(d + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() - 6); return t.toISOString().slice(0, 10); };
const weekText = () => `Week of ${fmtDay(weekStart(O.week)).replace(/ \d{4}$/, '')} to ${fmtDay(O.week)}`;
const others = (list, k = 3) => list.slice(0, k).map(name).map(esc).join(', ') + (list.length > k ? ` +${list.length - k}` : '');
function rowsTable(rows, fading, opts = {}) {
    const tr = (r, cls) => {
        const [topic, sub] = parts(r.g);
        const extra = [r.c && r.c.length ? esc(r.c.join(', ')) : '', opts.where && r.in && r.in.length ? 'in ' + others(r.in) : ''].filter(Boolean).join(' · ');
        return `<tr class="${cls}"><td class="lab"><small>${esc(topic)} · </small>${esc(sub)}${extra ? `<span class="cx">${extra}</span>` : ''}</td>
            <td class="num"><span class="x">${ratio(r.r)}</span><span class="n">${arts(r.n)}</span></td><td>${badge(r)}</td></tr>`;
    };
    return `<table class="rows">${rows.map(r => tr(r, '')).join('')}${fading.map(r => tr(r, 'fade')).join('')}</table>`;
}
function segHtml() {
    return `<div class="seg"><span>Compare with</span>${PERIODS.map(([, t], i) => `<button data-p="${i}" class="${i === per ? 'on' : ''}">${t}</button>`).join('')}</div>`;
}
function wireSeg(root, render) {
    root.querySelectorAll('.seg button').forEach(b => b.onclick = () => { per = +b.dataset.p; render(); });
}
"""

OVERVIEW_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>__SHARED_CSS__
.region { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 24px; }
.region h2 { font-size: 1.25em; margin-bottom: 2px; }
.kpis { display: flex; flex-direction: column; gap: 14px; border-right: 1px solid var(--soft); padding-right: 20px; }
.kpi .v { font-size: 1.9em; font-weight: 700; color: var(--accent); line-height: 1.1; }
.kpi .t { color: var(--muted); font-size: 12px; }
.kpi .d { font-size: 12px; font-weight: 600; }
.up { color: var(--green); } .down { color: var(--red); }
.head { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.head h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
.head .seg { margin-left: auto; }
.subs { margin-top: 16px; border-top: 1px solid var(--border); padding-top: 10px; }
.subrow { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 12px; padding: 7px 0; border-top: 1px solid var(--soft); }
.subrow:first-of-type { border-top: 0; }
.subrow .sn { font-weight: 700; }
.pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pill { border: 1px solid var(--border); border-radius: 4px; padding: 3px 8px; background: #fff; white-space: nowrap; }
.shared { margin-top: 5px; font-size: 12px; color: var(--muted); }
.shared b { color: var(--text); font-weight: 600; }
.country { cursor: pointer; color: var(--accent); font-weight: 600; border: 0; background: none; font-size: 13px; text-align: left; padding: 0; }
.country:hover { text-decoration: underline; }
h2.sec { font-size: 1.15em; margin: 22px 0 10px; }
details.sr { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 10px; }
details.sr summary { cursor: pointer; padding: 10px 16px; font-weight: 700; list-style-position: inside; }
details.sr summary small { color: var(--muted); font-weight: 400; margin-left: 6px; }
details.sr .body { padding: 0 16px 12px; }
table.ct { width: 100%; border-collapse: collapse; }
table.ct td { padding: 7px 6px; border-top: 1px solid var(--soft); vertical-align: top; }
table.ct td:first-child { width: 170px; }
table.ct td.ex { text-align: right; color: var(--muted); font-size: 11px; white-space: nowrap; width: 90px; }
@media (max-width: 760px) { .region { grid-template-columns: 1fr; } .kpis { border-right: 0; padding-right: 0; } }
</style>
</head>
<body>
<div class="top">
  <div>
    <h1>Topic bursts this week</h1>
    <div class="sub" id="window"></div>
  </div>
</div>
<div id="app"></div>
<script>__SHARED_JS__
const TOP = 8, SUB_TOP = 3, CTY_TOP = 5;
const open = new Set();
const signed = v => (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)).toLocaleString('en');
const unitScore = u => (O.units[u] ? O.units[u].rows : []).reduce((s, r) => s + score(r), 0);
const pill = r => `<span class="pill">${esc(parts(r.g)[1])} <span class="x">${ratio(r.r)}</span><span class="n">· ${r.n} art.</span> ${badge(r)}</span>`;
const more = (key, n, k) => n > k ? `<button class="more" data-k="${key}">${open.has(key) ? 'Show top ' + k : 'Show all ' + n}</button>` : '';
const cut = (key, list, k) => open.has(key) ? list : list.slice(0, k);

function kpis(k) {
    const usual = k.usual[per], d = usual ? (k.articles / usual - 1) * 100 : null;
    const dt = d === null ? '' : `<div class="d ${d >= 0 ? 'up' : 'down'}">${d >= 0 ? '+' : ''}${d.toFixed(0)}% vs avg week (${PERIODS[per][1]})</div>`;
    const n = Object.keys(NAMES).filter(c => !(c in O.subregions) && c !== O.region).length;
    return `<div class="kpis">
      <div class="kpi"><div class="v">${k.articles.toLocaleString('en')}</div><div class="t">articles this week</div>${dt}</div>
      <div class="kpi"><div class="v">${k.subtopics}</div><div class="t">subtopics bursting in at least one country</div></div>
      <div class="kpi"><div class="v">${k.countries}<small style="font-size:.5em;color:var(--muted)"> / ${n}</small></div><div class="t">countries with a burst</div></div>
      <div class="kpi"><div class="v">${k.new}</div><div class="t">new bursts (country × subtopic)</div></div>
    </div>`;
}

function subRow(s) {
    const u = O.units['subregion:' + s];
    if (!u) return '';
    const top = byScore(u.rows).slice(0, SUB_TOP);
    const shared = byScore(u.rows.filter(r => r.in && r.in.length >= 2));
    const key = 'sh:' + s;
    const sh = shared.length ? `<div class="shared">Shared: ${cut(key, shared, 3).map(r => `<b>${esc(parts(r.g)[1])}</b> (${others(r.in, 4)})`).join(' · ')} ${more(key, shared.length, 3)}</div>` : '';
    return `<div class="subrow"><div class="sn">${esc(name(s))}</div><div><div class="pills">${top.map(pill).join('') || '<span class="empty">No burst this week</span>'}</div>${sh}</div></div>`;
}

function countryTable(s) {
    const list = O.subregions[s].filter(c => O.units[c] && O.units[c].rows.length).sort((a, b) => unitScore(b) - unitScore(a));
    const quiet = O.subregions[s].length - list.length;
    const key = 'ct:' + s;
    const rows = cut(key, list, CTY_TOP).map(c => `<tr><td><button class="country" data-c="${c}">${esc(name(c))}</button></td>
        <td><div class="pills">${byScore(O.units[c].rows).slice(0, 3).map(pill).join('')}</div></td>
        <td class="ex">${signed(unitScore(c))} art.</td></tr>`).join('');
    return `<details class="sr" open><summary>${esc(name(s))}<small>${list.length} of ${O.subregions[s].length} countries bursting</small></summary>
      <div class="body">${list.length ? `<table class="ct">${rows}</table>` : '<div class="empty">No country bursting this week.</div>'}
      ${list.length > CTY_TOP ? `<button class="more" data-k="${key}">${open.has(key) ? 'Top ' + CTY_TOP + ' countries' : 'All countries (' + list.length + ')'}</button>` : ''}
      ${quiet && open.has(key) ? `<div class="empty">${quiet} with no burst this week.</div>` : ''}</div></details>`;
}

function render() {
    document.getElementById('window').textContent =
        `${weekText()}. "1.8× usual" = this week's coverage vs an average week of the comparison period (Baker index: each source standardized by its 2024 variation, averaged over sources that published in at least half of 2024's weeks; regions average their countries); "–" = none of those sources covers it this week. Below it, articles this week. Ranked by articles above an average week. "↑ N wks above 2024" = the 4-week average has stayed 1.5× its 2024 level for N weeks (long crises stop bursting). Updated ${O.generated}.`;
    const reg = O.units.region || {rows: [], fading: [], kpi: {articles: 0, usual: [0, 0, 0, 0], subtopics: 0, countries: 0, new: 0}};
    const rows = byScore(reg.rows);
    const fading = [...reg.fading].sort((a, b) => b.n - a.n).slice(0, 2);
    const states = Object.keys(O.subregions).filter(s => s in O.subregions);
    // Country table state is kept per subregion; a re-render keeps <details> open/closed.
    const closed = new Set([...document.querySelectorAll('details.sr')].filter(d => !d.open).map(d => d.dataset.s));
    document.getElementById('app').innerHTML = `
      <div class="card"><div class="region">${kpis(reg.kpi)}
        <div><div class="head"><div><h2>${esc(name(O.region))}</h2><h3>Top subtopics: bursting or persistent</h3></div>${segHtml()}</div>
          ${rowsTable(cut('reg', rows, TOP), fading, {where: true})}${more('reg', rows.length, TOP)}</div></div>
        <div class="subs">${states.map(subRow).join('')}</div></div>
      <h2 class="sec">Countries</h2>
      ${states.map(countryTable).join('')}`;
    document.querySelectorAll('details.sr').forEach((d, i) => { d.dataset.s = states[i]; if (closed.has(states[i])) d.open = false; });
    wireSeg(document, render);
    document.querySelectorAll('.more').forEach(b => b.onclick = () => { open.has(b.dataset.k) ? open.delete(b.dataset.k) : open.add(b.dataset.k); render(); });
    document.querySelectorAll('.country').forEach(b => b.onclick = () => {
        const doc = window.parent.document;
        doc.getElementById('r6').checked = true;
        doc.querySelector('#p6 iframe').contentWindow.setUnit(b.dataset.c, per);
    });
}
render();
</script>
</body>
</html>"""

COUNTRY_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>__SHARED_CSS__
.card h2 { font-size: 1.15em; margin-bottom: 8px; }
.note { color: var(--muted); margin-top: 10px; font-size: 12px; }
</style>
</head>
<body>
<div class="top">
  <div>
    <h1>Country overview</h1>
    <div class="sub" id="window"></div>
  </div>
  <div class="controls"><span id="seg"></span><select id="unit">__UNIT_OPTIONS__</select></div>
</div>
<div class="card" id="app"></div>
<script>__SHARED_JS__
const sel = document.getElementById('unit');
const key = v => v.startsWith('region:') ? 'region' : v;
function render() {
    document.getElementById('window').textContent = `${weekText()}. Every subtopic bursting or persistently above 2024 this week, then those that stopped bursting in the last 3 weeks. A fuller country view comes later.`;
    document.getElementById('seg').innerHTML = segHtml();
    wireSeg(document, render);
    const u = O.units[key(sel.value)];
    const label = sel.options[sel.selectedIndex].text.trim();
    document.getElementById('app').innerHTML = !u ? `<h2>${esc(label)}</h2><div class="empty">No topic burst this week or in the last 3 weeks.</div>`
        : `<h2>${esc(label)}</h2>${rowsTable(byScore(u.rows), [...u.fading].sort((a, b) => b.n - a.n), {where: true})}`;
}
// Called by the Overview tab when a country is clicked.
window.setUnit = (u, p) => {
    if ([...sel.options].some(o => o.value === u)) { sel.value = u; if (p !== undefined) per = p; render(); window.scrollTo(0, 0); }
};
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


def build_overview_html(overview: dict, names: dict) -> str:
    return _page(OVERVIEW_TEMPLATE, overview, names)


def build_country_html(overview: dict, unit_options_html: str, names: dict) -> str:
    return _page(
        COUNTRY_TEMPLATE.replace("__UNIT_OPTIONS__", unit_options_html),
        overview,
        names,
    )
