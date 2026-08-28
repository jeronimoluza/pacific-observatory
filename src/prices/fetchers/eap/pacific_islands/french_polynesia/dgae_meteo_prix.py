"""DGAE (Direction Generale des Affaires Economiques) — "La Meteo des Prix",
French Polynesia's official monthly multi-store price survey.

Published as one PDF per island/store-group edition (Tahiti hypers & grands
supermarches "HGS", Tahiti moyens & petits supermarches "MPS", Moorea "tous
supermarches", Raiatea "tous supermarches"), each listing 200+ everyday
consumer products with one price column per surveyed store. Discovered via
the WordPress media REST API (much more robust than scraping the listing
page's HTML, and gives a clean island/month/year from the attachment title):

    https://www.service-public.pf/dgae/wp-json/wp/v2/media?search=meteo

Table extraction is column-position based, not text-strategy: pdfplumber's
extract_tables() glues adjacent store-price columns into one string because
there are no ruling lines between them. Instead we cluster the x0 of every
numeric word in the price zone (bounded by the "Reference" header's right
edge and the "Prix le plus bas" header's left edge) into per-store columns,
then read the store name for each column off the header band directly above.

Known limitation: the Tahiti-MPS edition packs ~20 stores into the same page
width as the other editions' ~11, and prints store names as slanted two-line
text to fit. The column-clustering still recovers correct (item, price)
pairs for MPS, but the derived store label in `notes` occasionally blends
two adjacent stores' name fragments. Left in (rows are still valid — only
the free-text `notes` attribution is sometimes off) rather than dropped, but
flagged here for whoever revisits it.

COICOP: wide (groceries, dairy, produce, hygiene, ...) -> coicop_classification:
classifier. `coicop_code` is intentionally not populated.
Currency: XPF (CFP franc), confirmed both by countries.yaml and the PDF's own
"F CFP" column labels.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_WP_MEDIA_URL = "https://www.service-public.pf/dgae/wp-json/wp/v2/media"
_COUNTRY = "French Polynesia"
_CURRENCY = "XPF"
_SOURCE_KEY = "pf_dgae_meteo_prix"
_SOURCE_URL = "https://www.service-public.pf/dgae/releve-des-prix/la-meteo-des-prix/"
_UNIT = "each"
_IDENT = ["source_key", "observation_date", "item_name", "notes"]

# (group_key, subnational_area label, regex to match the WP attachment title)
_GROUPS = [
    ("tahiti_hgs", "Tahiti", re.compile(r"Tahiti\s*HGS", re.IGNORECASE)),
    ("tahiti_mps", "Tahiti", re.compile(r"Tahiti\s*MPS", re.IGNORECASE)),
    ("moorea", "Moorea", re.compile(r"Moorea", re.IGNORECASE)),
    ("raiatea", "Raiatea", re.compile(r"Raiatea", re.IGNORECASE)),
]

_FR_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _parse_month_year(title: str) -> tuple[int, int] | None:
    norm = _strip_accents(title).lower()
    m = re.search(r"(" + "|".join(_FR_MONTHS) + r")\D{0,3}(\d{4})", norm)
    if not m:
        return None
    return int(m.group(2)), _FR_MONTHS[m.group(1)]


def _list_latest_editions(session) -> dict[str, dict]:
    """Return {group_key: {"url", "title", "year", "month"}} for the newest
    attachment matching each group, using the WP REST media search
    (sorted newest-first by default)."""
    try:
        r = session.get(
            _WP_MEDIA_URL,
            params={
                "search": "meteo",
                "per_page": 60,
                "orderby": "date",
                "order": "desc",
            },
            timeout=60,
        )
        r.raise_for_status()
        items = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] WP media search failed: %s", _SOURCE_KEY, exc)
        return {}

    found: dict[str, dict] = {}
    for item in items:
        title = item.get("title", {}).get("rendered", "")
        url = item.get("guid", {}).get("rendered", "")
        if not title or not url or not url.lower().endswith(".pdf"):
            continue
        for group_key, area, pattern in _GROUPS:
            if group_key in found:
                continue
            if pattern.search(title):
                my = _parse_month_year(title)
                if my is None:
                    continue
                found[group_key] = {
                    "url": url,
                    "title": title,
                    "area": area,
                    "year": my[0],
                    "month": my[1],
                }
                break
    return found


def _cluster_1d(values: list[float], gap: float = 12.0) -> list[float]:
    values = sorted(values)
    clusters: list[list[float]] = [[values[0]]]
    for v in values[1:]:
        if v - clusters[-1][-1] <= gap:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters]


def _find_header_bounds(page) -> tuple[float, float, float] | None:
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    ref = next((w for w in words if w["text"] == "Référence"), None)
    if ref is None:
        return None
    zone_left = ref["x1"] + 5
    header_bottom = ref["top"] + 10
    prix_candidates = [
        w["x0"]
        for w in words
        if w["text"] == "Prix" and w["x0"] > 600 and w["top"] < header_bottom + 20
    ]
    zone_right = (min(prix_candidates) - 3) if prix_candidates else 1000.0
    return zone_left, zone_right, header_bottom


def _merge_thousands(num_words: list[dict]) -> list[dict]:
    """DGAE prices >= 1000 XPF render as two space-separated words, e.g.
    "1 550" -> word "1" (x0=398.2) + word "550" (x0=401.8), gap ~1pt. Left
    unmerged, naive first-token-per-column assignment keeps only the leading
    "1" and reports price=1 for a 1550 XPF item. Merge any numeric word pair
    that is (a) touching (gap < 4.5pt, far under the ~24pt+ store-to-store
    gap) and (b) shaped like <=3 digits followed by exactly 3 digits."""
    if not num_words:
        return []
    num_words = sorted(num_words, key=lambda w: w["x0"])
    merged: list[dict] = [dict(num_words[0])]
    for w in num_words[1:]:
        prev = merged[-1]
        gap = w["x0"] - prev["x1"]
        if gap < 4.5 and len(prev["text"]) <= 3 and len(w["text"]) == 3:
            prev["text"] = prev["text"] + w["text"]
            prev["x1"] = w["x1"]
        else:
            merged.append(dict(w))
    return merged


def _parse_pdf(pdf_bytes: bytes, group_key: str) -> list[dict]:
    """Extract (item_name, category, store_label, price_local) rows via
    x-position column clustering. See module docstring for why."""
    rows: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if not pdf.pages:
            return rows
        bounds = _find_header_bounds(pdf.pages[0])
        if bounds is None:
            logger.warning(
                "[%s] %s: could not locate 'Référence' header, skipping",
                _SOURCE_KEY,
                group_key,
            )
            return rows
        zone_left, zone_right, header_bottom = bounds
        header_top = header_bottom - 20

        # Build per-page line groups once (top-gap clustering), with
        # in-zone numeric tokens already thousands-merged, so both the
        # column-center pass and the row-extraction pass read the same data.
        pages_lines: list[list[list[dict]]] = []
        for page in pdf.pages:
            words = [
                w
                for w in page.extract_words(use_text_flow=False, keep_blank_chars=False)
                if w["top"] >= header_bottom
            ]
            words.sort(key=lambda w: w["top"])
            line_groups: list[list[dict]] = []
            cur: list[dict] = []
            last_top = None
            for w in words:
                if last_top is not None and w["top"] - last_top > 3:
                    line_groups.append(cur)
                    cur = []
                cur.append(w)
                last_top = w["top"]
            if cur:
                line_groups.append(cur)

            fixed_lines = []
            for ws in line_groups:
                ws.sort(key=lambda w: w["x0"])
                other = [w for w in ws if not (zone_left <= w["x0"] < zone_right)]
                num_in_zone = [
                    w
                    for w in ws
                    if zone_left <= w["x0"] < zone_right
                    and re.fullmatch(
                        r"\d[\d.,]*", w["text"].replace(" ", "").replace("\xa0", "")
                    )
                ]
                non_num_in_zone = [
                    w
                    for w in ws
                    if zone_left <= w["x0"] < zone_right
                    and not re.fullmatch(
                        r"\d[\d.,]*", w["text"].replace(" ", "").replace("\xa0", "")
                    )
                ]
                merged_num = _merge_thousands(num_in_zone)
                fixed_lines.append(other + non_num_in_zone + merged_num)
            pages_lines.append(fixed_lines)

        num_x0s: list[float] = []
        for fixed_lines in pages_lines:
            for ws in fixed_lines:
                for w in ws:
                    if zone_left <= w["x0"] < zone_right and re.fullmatch(
                        r"\d+", w["text"]
                    ):
                        num_x0s.append(w["x0"])
        if not num_x0s:
            logger.warning("[%s] %s: no price columns detected", _SOURCE_KEY, group_key)
            return rows
        centers = _cluster_1d(num_x0s)

        header_words = [
            w
            for w in pdf.pages[0].extract_words(
                use_text_flow=False, keep_blank_chars=False
            )
            if header_top <= w["top"] < header_bottom
            and zone_left <= w["x0"] < zone_right
        ]
        col_name_parts: dict[int, list[tuple[float, float, str]]] = {
            i: [] for i in range(len(centers))
        }
        for w in header_words:
            cx = (w["x0"] + w["x1"]) / 2
            idx = min(range(len(centers)), key=lambda i: abs(centers[i] - cx))
            if abs(centers[idx] - cx) < 18:
                col_name_parts[idx].append((round(w["top"]), w["x0"], w["text"]))
        col_names = []
        for i in range(len(centers)):
            bands: dict[float, list[tuple[float, str]]] = {}
            for top, x0, text in sorted(col_name_parts[i]):
                bands.setdefault(top, []).append((x0, text))
            band_strs = [
                "".join(t for _, t in sorted(toks)) for _, toks in sorted(bands.items())
            ]
            col_names.append(" ".join(band_strs) if band_strs else f"store_{i + 1}")

        raw_rows: list[
            tuple[str, str, int, float]
        ] = []  # (category, item_name, col_idx, price)
        for fixed_lines in pages_lines:
            for ws in fixed_lines:
                ws = sorted(ws, key=lambda w: w["x0"])
                left_words = [w for w in ws if w["x0"] < zone_left]
                tokens = [w["text"] for w in left_words]
                if not tokens:
                    continue
                seq_idx = next((i for i, t in enumerate(tokens) if t.isdigit()), None)
                if seq_idx is None:
                    continue
                category = " ".join(tokens[:seq_idx]).strip()
                item_name = " ".join(tokens[seq_idx + 1 :]).strip()
                if not item_name:
                    continue

                num_words = [
                    w
                    for w in ws
                    if zone_left <= w["x0"] < zone_right
                    and re.fullmatch(r"\d+", w["text"])
                ]
                if not num_words:
                    continue
                store_first: dict[int, str] = {}
                for w in num_words:
                    cx = (w["x0"] + w["x1"]) / 2
                    idx = min(range(len(centers)), key=lambda i: abs(centers[i] - cx))
                    if abs(centers[idx] - cx) < 16 and idx not in store_first:
                        store_first[idx] = w["text"]
                for idx, tok in store_first.items():
                    try:
                        val = float(tok)
                    except ValueError:
                        continue
                    if val <= 0:
                        continue
                    raw_rows.append((category, item_name, idx, val))

        if not raw_rows:
            return rows

        # Drop noise columns: a real store column carries most of the
        # catalog; a stray mis-tokenized decimal produces a 1-2 row column.
        counts: dict[int, int] = {}
        for _, _, idx, _ in raw_rows:
            counts[idx] = counts.get(idx, 0) + 1
        median_count = sorted(counts.values())[len(counts) // 2]
        keep_idx = {i for i, c in counts.items() if c >= max(5, 0.15 * median_count)}

        for category, item_name, idx, val in raw_rows:
            if idx not in keep_idx:
                continue
            rows.append(
                {
                    "category": category,
                    "item_name": item_name,
                    "store_label": col_names[idx],
                    "price_local": val,
                }
            )
    return rows


def fetch_pf_dgae_meteo_prix(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    editions = _list_latest_editions(session)
    if not editions:
        logger.warning("[%s] no editions discovered", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    frames: list[pd.DataFrame] = []
    for group_key, edition in editions.items():
        obs_date = date(edition["year"], edition["month"], 1)
        if obs_date <= cutoff:
            logger.info(
                "[%s] %s: %s <= cutoff %s, skipping",
                _SOURCE_KEY,
                group_key,
                obs_date,
                cutoff,
            )
            continue
        try:
            r = session.get(edition["url"], timeout=120)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] %s: download failed: %s", _SOURCE_KEY, group_key, exc)
            continue

        parsed = _parse_pdf(r.content, group_key)
        if not parsed:
            logger.warning(
                "[%s] %s: 0 rows parsed from %s", _SOURCE_KEY, group_key, edition["url"]
            )
            continue

        df = pd.DataFrame(parsed)
        out = pd.DataFrame(
            {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": df["item_name"],
                "price_local": df["price_local"].round(2),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": edition["url"],
                "notes": (
                    f"area={edition['area']}; category="
                    + df["category"]
                    + f"; edition={group_key}; store="
                    + df["store_label"]
                ),
                "scrape_ts": ts,
            }
        )
        out["observation_hash"] = out.apply(
            lambda row: make_hash(row.to_dict(), _IDENT), axis=1
        )
        frames.append(out)
        logger.info(
            "[%s] %s (%s) -> %d rows", _SOURCE_KEY, group_key, obs_date, len(out)
        )

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)
