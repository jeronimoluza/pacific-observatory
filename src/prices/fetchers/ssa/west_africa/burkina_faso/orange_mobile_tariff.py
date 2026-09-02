"""Burkina Faso Orange -- mobile commercial-offers tariff catalog, snapshot.

Orange Burkina publishes a "Canevas du catalogue des offres commerciales de
detail des reseaux mobiles" PDF -- a standardized template ARCEP (the telecom
regulator) requires operators to publish, linked from
https://www.orange.bf/fr/offres-mobiles.html. Verified live 2026-09-01: 200,
742,809 bytes, 35 pages, genuinely tabular (pdfplumber `extract_tables()`
recovers clean rows, not a scanned document). Sections cover: acquisition
offers, Voix (voice) passes, Data passes, SMS passes, roaming, and
international passes -- each with a "Prix FCFA TTC" (tax-included) column
and an "N deg" catalog number the regulator's canevas format mandates, many
rows also carrying a "Ref ARCEP: NNN/ARCEP/O(B|R)" regulatory filing
reference.

No archive of prior catalog versions was found -- like the ONEA tariff, this
fetcher snapshots the CURRENT catalog each run (`period_kind:
effective_from`), not a walked history.

Table shapes vary by section (Voix/SMS pages use N/Appellation/Souscription/
Volume/Prix/..., Data pages insert an extra Categorie column before
Appellation/Type) and pdfplumber's `extract_tables()` further splits each
section into many small borderless fragments that do not each repeat a
header row. So this fetcher does not assume a header at all: for every
extracted table fragment it auto-detects the price column (the column with
the most cells that parse as a strict XOF number, excluding the "N deg"
row-number column).

IDENTITY: the catalog's own "Appellation" column is frequently a SECTION
NAME shared by several distinct plans, not a plan identifier by itself --
e.g. four different "Forfaits Mois" rows priced 1050/1575/4200/10000 XOF,
distinguished only by a separate volume column ("1024 Mo"/"2048 Mo"/
"5,5 Go"/"20 Go"); four "Pass International" rows priced 263/552/1077/1050
XOF distinguished only by a duration+destination column ("5min (OCI, OFR)
+ ..."/"10min ..."/etc). An earlier version of this fetcher used the bare
Appellation text plus a positional "(2)"/"(3)" suffix for these -- that
collapsed distinct plans onto the same `item_name` (6 duplicate
observation_hash values out of 85 rows, confirmed by the wave-9 coordinator
review) and the positional suffix was not even stable across runs (it
renumbers if the PDF's row order changes). Fixed by pulling a genuine
SECOND identifying column per table fragment: whichever non-price,
non-USSD-code column has the highest ratio of distinct values among the
rows sharing that fragment (this recovers the volume/duration column in
both examples above, since it is scored on how well it discriminates rows
in that specific section, not by position). `item_name` is then
"<Appellation> <discriminator>", e.g. "Forfaits Mois 1024 Mo" / "Forfaits
Mois 2048 Mo" -- both stable across runs (drawn straight from the PDF's own
text, not from row order).

Belt-and-braces: after building every row's `item_name` across the whole
document, any name that STILL maps to more than one distinct price is
dropped entirely (logged by name) rather than shipped with a colliding
hash -- see `_drop_ambiguous`. On the 2026-09-01 catalog this fires on
zero names; the fix above resolved all 6 real collisions on its own.

CURRENCY: XOF, no minor unit for the vast majority of rows ("1 575" is 1,575
XOF), but a handful of per-second billing/fee rows in the source itself
carry a French-decimal-comma value (e.g. "52,5F" -- Transfert de Bonus fee),
which is parsed as 52.5 XOF rather than truncated or treated as a thousands
separator.

coicop_classification: source_curated -- the whole catalog is
telecommunication services, COICOP 08.3.0, regardless of plan type (voice,
SMS, data, roaming all fall under 08.3 in COICOP 2018 -- there is no
separate telecom sub-split by service type).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Burkina Faso"
_SOURCE_KEY = "orange_mobile_tariff_bf"
_PDF_URL = (
    "https://www.orange.bf/burkina_pages/uploads/1/other/"
    "CANEVAS_catalogue_offres_commerciales_detail_reseaux_mobiles.pdf"
)
_SOURCE_PAGE = "https://www.orange.bf/fr/offres-mobiles.html"
_EFFECTIVE_FROM = date(2026, 8, 1)
_COICOP_CODE = "08.3.0"
_IDENT = ["source_key", "observation_date", "item_name"]

# A cell counts as a strict price cell only if, once FCFA/TTC/F noise is
# stripped, what is left is ENTIRELY a number (space thousands separator,
# optional comma decimal) -- not "contains a digit somewhere", which would
# also match free-text volume/duration cells like "10 jours" or "120min
# (tous reseaux)".
_STRICT_PRICE_RE = re.compile(r"^\d[\d\s]*(?:,\d+)?$")
_LETTERS_RE = re.compile(r"[A-Za-z]{3,}")
_USSD_RE = re.compile(r"^\*|#")
_ALPHA_RE = re.compile(r"[A-Za-z\u00C0-\u00FF]")


def _clean(text) -> str:
    text = "" if text is None else str(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_xof(raw) -> float | None:
    # Some price cells carry a per-unit suffix after a slash, e.g.
    # "210F/SMS" or "53F/Jour" (premium SMS/VAS subscription rows) --
    # keep only the amount before the slash. A genuinely two-tiered price
    # cell like "0F (1ere inscr.) / 500F (suivantes)" also hits this split
    # and is then rejected by the strict-number check below (the
    # remaining "(1ere inscr.)" text does not parse) -- correctly dropped
    # rather than guessed at.
    s = _clean(raw).split("/", 1)[0].strip()
    s = s.upper().replace("TTC", "").replace("FCFA", "").replace("F", "")
    s = s.strip()
    if not s or not _STRICT_PRICE_RE.match(s):
        return None
    whole, _, frac = s.partition(",")
    whole = re.sub(r"\s", "", whole)
    if not whole:
        return None
    try:
        value = float(whole)
        if frac:
            value += float(frac) / (10 ** len(frac))
        return value
    except ValueError:
        return None


def _is_ussd(text: str) -> bool:
    return bool(_USSD_RE.search(text))


def _rows_from_table(table: list, page_num: int, table_idx: int) -> list[dict]:
    if not table:
        return []
    n_cols = max(len(r) for r in table)

    # Score each column by (hit count, distinct-value count). A real price
    # column has many distinct values; small integer flag columns like
    # "Prio. Voix"/"Prio. SMS" (values 1-3 only) parse as strict numbers too
    # but repeat the same 1-3 values across almost every row, so they lose
    # on the distinct-value tiebreak even when they have more hits.
    # Column 0 is the catalog's own "N deg" row-number column in every
    # observed table shape (always present, always small, always
    # near-unique) -- it parses as a "price" with plenty of distinct values
    # too, so it has to be excluded explicitly rather than left to the
    # scoring below to sort out.
    # Also track, per column, what fraction of its RAW (pre-strip) cells
    # carry an actual currency marker ("F"/"FCFA"). Most price cells here
    # are bare digits ("1050", "1 575") with no marker at all, so this
    # can't be a hard requirement -- but a handful of tables (premium
    # SMS/VAS subscriptions) ALSO carry a purely-numeric non-price column
    # (an SMS short code, e.g. "3166") that is just as strict-numeric and
    # just as unique as the real price -- without this tiebreak the short
    # code wins the distinct-value scoring below and gets shipped as the
    # XOF price, which is a currency-unit bug, not just an identity one.
    # Preferring the marker when one exists costs nothing on the majority
    # of tables where no column has it (the tiebreak is simply absent).
    col_values: dict[int, list[float]] = {c: [] for c in range(1, n_cols)}
    marker_hits: dict[int, int] = {c: 0 for c in range(1, n_cols)}
    for row in table:
        for c in range(1, min(len(row), n_cols)):
            v = _parse_xof(row[c])
            if v is not None:
                col_values[c].append(v)
                raw = _clean(row[c]).upper()
                if "F" in raw:
                    marker_hits[c] += 1
    if not any(col_values.values()):
        return []
    price_idx = max(
        col_values,
        key=lambda c: (
            marker_hits[c] >= max(1, len(col_values[c]) // 2),
            len(set(col_values[c])) >= 4,
            len(col_values[c]),
        ),
    )
    if len(col_values[price_idx]) < 1 or len(set(col_values[price_idx])) < 4:
        return []

    candidate_rows = [
        row
        for row in table
        if price_idx < len(row) and _parse_xof(row[price_idx]) is not None
    ]
    if not candidate_rows:
        return []

    # Primary name column: the non-price column with the most cells that
    # carry real text (letters) -- typically "Appellation"/"Categorie",
    # the section label shared by several plans.
    text_hits = {c: 0 for c in range(n_cols) if c != price_idx}
    for row in candidate_rows:
        for c in text_hits:
            if c < len(row) and _LETTERS_RE.search(_clean(row[c])):
                text_hits[c] += 1
    if not text_hits or max(text_hits.values()) == 0:
        return []
    primary_idx = max(text_hits, key=text_hits.get)

    # Secondary (discriminator) column: `primary_idx` (e.g. "Categorie")
    # is usually shared by SEVERAL rows -- "Forfaits Mois" alone covers 4
    # differently-priced plans in the source. The discriminator must
    # distinguish rows WITHIN each primary group, not just look varied
    # across the whole table -- a global distinct-value ratio is the wrong
    # metric here: it rewards a column like "Autres infos" (a per-row
    # regulatory "Ref ARCEP: NNN/ARCEP/OB" filing number, unique on every
    # row of the WHOLE table) over the actual attribute column ("Volume",
    # e.g. "1024 Mo"/"150 Mo"), because Volume repeats ACROSS primary
    # groups (a "150 Mo" daily pass and a "150 Mo" weekly pass both exist)
    # even though it is perfectly unique WITHIN each group. So: group rows
    # by their primary text first, then require full uniqueness inside
    # every group of size > 1.
    groups: dict[str, list[list]] = {}
    for row in candidate_rows:
        key = _clean(row[primary_idx]) if primary_idx < len(row) else ""
        groups.setdefault(key, []).append(row)

    best_secondary_idx = None
    for c in sorted(range(n_cols)):
        if c in (price_idx, primary_idx):
            continue
        vals_all = [_clean(row[c]) for row in candidate_rows if c < len(row)]
        vals_all = [v for v in vals_all if v]
        if len(vals_all) < 2:
            continue
        ussd_fraction = sum(1 for v in vals_all if _is_ussd(v)) / len(vals_all)
        if ussd_fraction > 0.3:
            continue
        # A real discriminator carries a plan ATTRIBUTE in words ("1024
        # Mo", "5,5 Go", "5min (OCI, OFR) + ..."), not a bare number --
        # otherwise the "N deg" row-number column would win by being
        # trivially unique, which is the same positional-suffix problem
        # this fix is meant to remove, just relocated.
        alpha_fraction = sum(1 for v in vals_all if _ALPHA_RE.search(v)) / len(vals_all)
        if alpha_fraction < 0.5:
            continue
        resolves_every_group = True
        for group_rows in groups.values():
            if len(group_rows) < 2:
                continue
            group_vals = [_clean(r[c]) if c < len(r) else "" for r in group_rows]
            if "" in group_vals or len(set(group_vals)) != len(group_vals):
                resolves_every_group = False
                break
        if resolves_every_group:
            # Lowest resolving column index wins: descriptive attribute
            # columns (Volume, Souscription, Volume services) sit right
            # next to the plan name in every observed table shape, while
            # a free-text regulatory reference is always the LAST column
            # ("Autres infos") -- preferring the earliest resolving column
            # favours the human-meaningful attribute over the filing
            # number when both happen to work.
            best_secondary_idx = c
            break

    out: list[dict] = []
    for row in candidate_rows:
        price = _parse_xof(row[price_idx])
        if price is None or price <= 0:
            continue
        primary = _clean(row[primary_idx]) if primary_idx < len(row) else ""
        if not primary or not _LETTERS_RE.search(primary):
            continue
        secondary = ""
        if best_secondary_idx is not None and best_secondary_idx < len(row):
            secondary = _clean(row[best_secondary_idx])
        item_name = (
            f"{primary} {secondary}".strip()
            if secondary and secondary != primary
            else primary
        )
        out.append(
            {
                "item_name": item_name[:200],
                "price_local": price,
                "notes": f"Orange BF mobile commercial-offers catalog, page {page_num}, table {table_idx}",
            }
        )
    return out


def _drop_ambiguous(parsed: list[dict]) -> list[dict]:
    """Drop any item_name that still maps to more than one distinct price.

    A name that cannot be told apart from a same-named neighbour is not a
    usable tariff row regardless of whether the observation_hash happens to
    collide or not -- ship nothing for it rather than pick one arbitrarily.
    """
    prices_by_name: dict[str, set[float]] = {}
    for p in parsed:
        prices_by_name.setdefault(p["item_name"], set()).add(p["price_local"])
    ambiguous = {name for name, prices in prices_by_name.items() if len(prices) > 1}
    if ambiguous:
        logger.warning(
            "[%s] dropping %d ambiguous item_name(s) with >1 distinct price: %s",
            _SOURCE_KEY,
            len(ambiguous),
            sorted(ambiguous),
        )
    return [p for p in parsed if p["item_name"] not in ambiguous]


def fetch_orange_mobile_tariff_bf(cutoff: date) -> pd.DataFrame | None:
    if _EFFECTIVE_FROM <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    try:
        resp = session.get(_PDF_URL, timeout=90)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF fetch failed: %s", _SOURCE_KEY, exc)
        return None

    import pdfplumber

    parsed: list[dict] = []
    try:
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    tables = page.extract_tables()
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "[%s] page %d table extraction failed: %s",
                        _SOURCE_KEY,
                        page_num,
                        exc,
                    )
                    continue
                for table_idx, table in enumerate(tables, start=1):
                    parsed.extend(_rows_from_table(table, page_num, table_idx))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF parse failed: %s", _SOURCE_KEY, exc)
        return None

    if not parsed:
        logger.warning("[%s] no plan rows parsed from %s", _SOURCE_KEY, _PDF_URL)
        return None

    parsed = _drop_ambiguous(parsed)
    if not parsed:
        logger.warning("[%s] all rows dropped as ambiguous", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": _EFFECTIVE_FROM.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": "XOF",
            "unit": "plan",
            "source_url": _PDF_URL,
            "notes": p["notes"],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
