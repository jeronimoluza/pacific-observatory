"""kontrakt.edu.uz — Uzbekistan Ministry of Higher Education contract (tuition)
price registry. Public unauthenticated REST API, one POST per organization.
"""

import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_BASE = "https://kontrakt-api.edu.uz"
_COUNTRY = "Uzbekistan"
_CURRENCY = "UZS"
_SOURCE_KEY = "uz_kontrakt_edu_prices"
_COICOP = "10.4.0"  # Tertiary education

# Scope: current academic year, Bakalavr (undergraduate), 1st stage/year,
# Kunduzgi ta'lim (full-time) — the headline "kontrakt narxi" figure every
# organization publishes. Magistr/Ordinatura/Doktorantura and other forms
# (sirtqi/kechki/masofaviy) are a deliberate scope cut for v1; widen the
# eduTypeId/eduFormId/eduLevelId loop if those are wanted later.
_EDU_TYPE_ID = 1  # Bakalavr
_EDU_LEVEL_ID = 1  # 1-bosqich
_EDU_FORM_ID = 1  # Kunduzgi ta'lim

_IDENT = ["source_key", "observation_date", "item_name"]


def _current_edu_year(session) -> tuple[int, str, date]:
    resp = session.get(f"{_API_BASE}/manual/EduYearSelectList", timeout=30)
    resp.raise_for_status()
    years = resp.json()
    current = next((y for y in years if y.get("isCurrent")), years[0])
    m = re.search(r"(\d{4})", current["text"])
    start_year = int(m.group(1)) if m else datetime.now(timezone.utc).year
    return current["value"], current["text"], date(start_year, 9, 1)


def _organizations(session, edu_year_id: int) -> list[dict]:
    resp = session.get(
        f"{_API_BASE}/SpecialityPriceReport/OrganizationSelectList",
        params={"eduYearId": edu_year_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_uz_kontrakt_edu_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    edu_year_id, edu_year_text, effective_from = _current_edu_year(session)
    if effective_from <= cutoff:
        return None

    orgs = _organizations(session, edu_year_id)

    rows = []
    for org in orgs:
        org_id = org["value"]
        org_name = org["text"].split(" - ", 1)[-1].strip()

        try:
            resp = session.post(
                f"{_API_BASE}/SpecialityPriceReport/GetList",
                json={
                    "eduYearId": edu_year_id,
                    "organizationId": org_id,
                    "eduTypeId": _EDU_TYPE_ID,
                    "eduLevelId": _EDU_LEVEL_ID,
                    "eduFormId": _EDU_FORM_ID,
                },
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("kontrakt.edu.uz fetch failed for org %r: %s", org_name, exc)
            continue

        if resp.status_code != 200:
            # Org has no Bakalavr / full-time offering at this level — expected, not an error.
            continue

        payload = resp.json()
        for item in payload.get("rows", []):
            price = item.get("baseAmountWithoutStipend")
            speciality = item.get("name")
            if price is None or not speciality:
                continue
            item_name = f"{org_name}: {speciality}"
            row = {
                "observation_date": effective_from.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": float(price),
                "currency": _CURRENCY,
                "unit": "year",
                "coicop_code": _COICOP,
                "effective_from": effective_from.isoformat(),
                "source_url": f"{_API_BASE}/SpecialityPriceReport/GetList?organizationId={org_id}",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

        time.sleep(0.2)

    return pd.DataFrame(rows) if rows else None
