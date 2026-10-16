"""GlobalPetrolPrices (GPP) as a REFERENCE for `po fuel watch`, never as data.

GPP's methods are unknown, so nothing here reaches observations or publish: the
fetched values go to data/fuel/_reference/gpp/<country>.csv (reference_only=true)
and are only compared against our own latest level to raise alerts.

GPP serves two page layouts and, for countries it no longer follows, a page with an
old date or a 0.000 price under HTTP 200. `parse_page` refuses all of those, so a
dead GPP page shows up as a broken watch, not as a silent "no change".
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime, timezone
from pathlib import Path

URL = "https://www.globalpetrolprices.com/{slug}/{product}_prices/"
REF_COLUMNS = [
    "gpp_date",
    "product",
    "price_local",
    "currency",
    "unit",
    "fetched_at",
    "url",
    "reference_only",
]

_H1 = re.compile(r"<h1>\s*(.*?)\s*</h1>", re.S)
_DATE = re.compile(r"(\d{2}-[A-Z][a-z]{2}-\d{4})")
# Layout A: a table whose first body row is "&nbsp;BWP | 18.210 | 68.932" (liter, gallon).
_ROW_A = re.compile(r'<th height="30">&nbsp;([A-Z]{3})</th>\s*<td[^>]*>([\d,.]+)</td>')
# Layout B: "... in the  Ivory Coast is  XOF 905.00 per liter ... updated on 12-Oct-2026" (gasoline)
# or "... based on the latest update from 12-Oct-2026" (diesel).
_SENT_B = re.compile(
    r"\bis\s+([A-Z]{3})\s+([\d,.]+)\s+per liter.{0,200}?(\d{2}-[A-Z][a-z]{2}-\d{4})",
    re.S,
)


class GPPError(Exception):
    """A GPP page that cannot be trusted as a reference (stale, zero, wrong country)."""


def parse_page(
    html: str, *, name: str, currency: str, max_age_days: int, today: date | None = None
) -> tuple[date, float]:
    """(gpp_date, price per liter in local currency) or GPPError."""
    today = today or datetime.now(timezone.utc).date()
    h1 = _H1.search(html)
    if not h1 or name.lower() not in h1.group(1).lower():
        raise GPPError(
            f"h1 does not name {name!r}: {h1.group(1)[:80] if h1 else 'no h1'}"
        )
    m = _SENT_B.search(html)
    if m:
        cur, val, d = m.group(1), m.group(2), m.group(3)
    else:
        row, d = _ROW_A.search(html), _DATE.search(h1.group(1))
        if not row or not d:
            raise GPPError("no price row in either GPP layout")
        cur, val, d = row.group(1), row.group(2), d.group(1)
    price = float(val.replace(",", ""))
    when = datetime.strptime(d, "%d-%b-%Y").date()
    if cur != currency:
        raise GPPError(f"currency {cur} != {currency}")
    if price <= 0:
        raise GPPError(f"price {price} <= 0 (GPP does not follow this country)")
    if (today - when).days > max_age_days:
        raise GPPError(f"GPP date {when} older than {max_age_days} days")
    return when, price


def append_reference(path: Path, rows: list[dict]) -> int:
    """Append new (gpp_date, product) rows to the reference CSV; return how many were new."""
    seen = set()
    if path.exists():
        with open(path, newline="") as f:
            seen = {(r["gpp_date"], r["product"]) for r in csv.DictReader(f)}
    new = [r for r in rows if (r["gpp_date"], r["product"]) not in seen]
    if not new:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REF_COLUMNS)
        if fresh:
            w.writeheader()
        w.writerows(new)
    return len(new)


def _pct(a: float, b: float) -> float:
    return abs(a / b - 1) * 100


def compare(
    product: str,
    gpp_date: date,
    gpp: float,
    ours: tuple[date, float] | None,
    st: dict,
    cfg: dict,
) -> list[tuple[str, str, str]]:
    """Alerts (severity, key, message) for one product; updates `st` (this product's state).

    - move: our level unchanged while GPP moved > move_pct since our level last changed
      -> "posible ajuste no cargado".
    - divergence: our level and GPP differ > diverge_pct on diverge_runs distinct GPP dates.
    - no table yet: any change of the GPP value is the only signal we have.
    Keys carry the values involved, so the same situation alerts once, a new one again.
    """
    out = []
    move, div, runs = (
        cfg.get("move_pct", 3),
        cfg.get("diverge_pct", 5),
        cfg.get("diverge_runs", 3),
    )
    prev = st.get("last")
    st["last"] = {"date": gpp_date.isoformat(), "value": gpp}
    if ours is None:
        if prev and prev["value"] != gpp:
            out.append(
                (
                    "amarillo",
                    f"gppchg:{product}:{gpp:g}",
                    f"GPP {product} {prev['value']:g} -> {gpp:g} ({prev['date']} -> {gpp_date}); "
                    "sin tabla propia: buscar el anuncio oficial",
                )
            )
        return out
    our_date, our = ours
    anchor = st.get("anchor")
    if not anchor or anchor["our_date"] != our_date.isoformat():
        st["anchor"] = {
            "our_date": our_date.isoformat(),
            "gpp": gpp,
            "gpp_date": gpp_date.isoformat(),
        }
    elif _pct(gpp, anchor["gpp"]) > move:
        out.append(
            (
                "amarillo",
                f"move:{product}:{our_date}:{gpp:g}",
                f"posible ajuste no cargado: GPP {product} {anchor['gpp']:g} -> {gpp:g} "
                f"({_pct(gpp, anchor['gpp']):.1f}% > {move}%) y nuestro nivel sigue en {our:g} desde {our_date}",
            )
        )
    if _pct(our, gpp) > div:
        if st.get("div_last_date") != gpp_date.isoformat():
            st["div_runs"] = st.get("div_runs", 0) + 1
            st["div_last_date"] = gpp_date.isoformat()
        if st["div_runs"] >= runs:
            out.append(
                (
                    "amarillo",
                    f"div:{product}:{our:g}:{gpp:g}",
                    f"divergencia: nuestro {product} {our:g} ({our_date}) vs GPP {gpp:g} ({gpp_date}), "
                    f"{_pct(our, gpp):.1f}% > {div}% en {st['div_runs']} fechas GPP seguidas",
                )
            )
    else:
        st["div_runs"], st["div_last_date"] = 0, None
    return out
