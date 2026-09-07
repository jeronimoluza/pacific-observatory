"""American Samoa Power Authority monthly utility billing rates."""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from urllib.parse import urljoin

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_aspa_utility_rates"
_RATES_URL = "https://www.aspower.com/rates.html"
_IDENT = ["source_key", "observation_date", "item_name"]

_PDF_HREF_RE = re.compile(r'href="(?P<href>ASPAWEB/rates/\d{6}_FS1?\.pdf)"', re.I)
_BILLING_MONTH_RE = re.compile(
    r"Billing Rates for (?P<month>[A-Za-z]+)\s+(?P<year>\d{4})", re.I
)
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_MONEY_UNIT_RE = re.compile(
    r"\$(?P<price>\d+(?:\.\d+)?)\s*/\s*(?P<unit>pound|cubic yard|1,000 gals)",
    re.I,
)
_ELECTRIC_RATE_RE = re.compile(
    r"0\.002\s+"
    r"(?P<energy_base>\d+\.\d+)\s+"
    r"(?P<total_energy>\d+\.\d+)\s+"
    r"(?P<fuel_surcharge>\d+\.\d+)\s+"
    r"(?P<system_rate>0\.\d+)"
    r"(?:\s+\$\d+(?:\.\d+)?/kW)?"
    r"(?:\s+(?P<service_charge>\d+(?:\.\d+)?))?\s*$",
    re.I,
)
_WATER_RATE_RE = re.compile(
    r"^(?P<label>Commercial:|0 to 10,000|10,001 to 20,000|20,001 to 30,000|Above 30,000 gals)\s+"
    r"(?P<base>0\.\d+)\s+"
    r"(?P<surcharge>0\.\d+)\s+"
    r"(?P<system>0\.\d+)"
    r"(?:\s+per gal\s+(?P<service>\d+(?:\.\d+)?))?\s*$",
    re.I,
)
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_ELECTRIC_LABELS = (
    "Gov't. Residential",
    "Residential",
    "Gov't. Small General Service",
    "Small General Service - Private",
    "ASPA Small Gen Svce",
    "Gov't. Large General Service",
    "Large General Service - Private",
    "ASPA Large Gen Svce",
    "Small General Service",
    "Large General Service",
    "Industrial 1 - 1st 1,000,000",
    "Industrial 2 - Over 1,000,000",
)


def _clean_line(line: str) -> str:
    return re.sub(r"\b0\s+\.", "0.", line.strip())


def _month_from_text(text: str) -> date | None:
    m = _BILLING_MONTH_RE.search(text)
    if not m:
        return None
    month = _MONTHS.get(m.group("month").lower())
    if not month:
        return None
    return date(int(m.group("year")), month, 1)


def _row(
    obs_date: date,
    item_name: str,
    price: float,
    unit: str,
    coicop_code: str,
    source_url: str,
    notes: str,
    ts: str,
) -> dict:
    out = {
        "observation_date": obs_date.isoformat(),
        "period_kind": "monthly_tariff",
        "country": _COUNTRY,
        "source_key": _SOURCE_KEY,
        "coicop_code": coicop_code,
        "item_name": item_name,
        "price_local": round(price, 6),
        "currency": _CURRENCY,
        "unit": unit,
        "source_url": source_url,
        "notes": notes,
        "scrape_ts": ts,
        "observation_hash": None,
    }
    out["observation_hash"] = make_hash(out, _IDENT)
    return out


def _electric_label(line: str) -> str | None:
    matches = [label for label in _ELECTRIC_LABELS if line.startswith(label)]
    if not matches:
        return None
    return max(matches, key=len)


def _parse_pdf(text: str, obs_date: date, source_url: str) -> list[dict]:
    ts = get_scrape_ts()
    rows: list[dict] = []
    section = "electric"
    disposal_group = ""

    for raw in text.splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        if line.startswith("Streetlight Charges"):
            section = "streetlight"
            continue
        if line.startswith("Water Total System"):
            section = "water"
            continue
        if line.startswith("Solidwaste System Rate"):
            section = "solidwaste"
            continue
        if line.startswith("Disposal Facility Fees"):
            section = "disposal"
            disposal_group = ""
            continue
        if "Groundwater Protection" in line or line.startswith("Service Charge per"):
            section = "groundwater"
            continue

        if section == "electric":
            label = _electric_label(line)
            if not label:
                continue
            rate = _ELECTRIC_RATE_RE.search(line)
            if not rate:
                continue
            system_rate = float(rate.group("system_rate"))
            rows.append(
                _row(
                    obs_date,
                    f"Electricity, {label.lower()}, system rate",
                    system_rate,
                    "kWh",
                    "04.5.1",
                    source_url,
                    "additional_renewable=0.002; "
                    f"energy_base={rate.group('energy_base')}; "
                    f"total_energy={rate.group('total_energy')}; "
                    f"fuel_surcharge={rate.group('fuel_surcharge')}",
                    ts,
                )
            )
            if rate.group("service_charge"):
                rows.append(
                    _row(
                        obs_date,
                        f"Electricity, {label.lower()}, service charge",
                        float(rate.group("service_charge")),
                        "meter_month",
                        "04.5.1",
                        source_url,
                        "service charge per meter",
                        ts,
                    )
                )
            continue

        if section == "streetlight":
            if line.startswith("Water "):
                section = "water"
                continue
            nums = [float(n) for n in _NUM_RE.findall(line)]
            if not nums:
                continue
            label = _NUM_RE.sub("", line, count=1).strip(" -") if line[0].isdigit() else line.rsplit(" ", 1)[0]
            rows.append(
                _row(
                    obs_date,
                    f"Streetlight charge, {label.strip()}",
                    nums[-1],
                    "month",
                    "04.5.1",
                    source_url,
                    "streetlight monthly charge",
                    ts,
                )
            )
            continue

        if section == "water":
            if line.startswith("Solidwaste "):
                section = "solidwaste"
                continue
            rate = _WATER_RATE_RE.match(line)
            if not rate:
                continue
            label = rate.group("label").rstrip(":")
            if label == "Commercial":
                label = "Commercial water"
            rows.append(
                _row(
                    obs_date,
                    f"Water, {label.lower()}, system rate",
                    float(rate.group("system")),
                    "gal",
                    "04.4.1",
                    source_url,
                    f"water_base={rate.group('base')}; surcharge={rate.group('surcharge')}",
                    ts,
                )
            )
            if rate.group("service"):
                rows.append(
                    _row(
                        obs_date,
                        f"Water, {label.lower()}, service charge",
                        float(rate.group("service")),
                        "meter_month",
                        "04.4.1",
                        source_url,
                        "water service charge",
                        ts,
                    )
                )
            continue

        if section == "solidwaste":
            if line.startswith("Small & Large General Services"):
                continue
            nums = [float(n) for n in _NUM_RE.findall(line)]
            if not nums:
                continue
            label = line.rsplit(" ", 1)[0].strip()
            rows.append(
                _row(
                    obs_date,
                    f"Solid waste, {label.lower()}",
                    nums[-1],
                    "month",
                    "04.4.2",
                    source_url,
                    "solid waste system rate",
                    ts,
                )
            )
            continue

        if section == "disposal":
            if line.startswith("Small & Large General Services"):
                disposal_group = "small and large general services"
                continue
            if line.startswith("Industrial Services"):
                disposal_group = "industrial services"
                continue
            m = _MONEY_UNIT_RE.search(line)
            if not m:
                continue
            label = line[: m.start()].strip()
            if disposal_group:
                label = f"{disposal_group}, {label}"
            rows.append(
                _row(
                    obs_date,
                    f"Disposal facility fee, {label.lower()}",
                    float(m.group("price")),
                    m.group("unit").lower(),
                    "04.4.2",
                    source_url,
                    "disposal facility fee",
                    ts,
                )
            )
            continue

        if section == "groundwater":
            nums = [float(n) for n in _NUM_RE.findall(line)]
            if not nums:
                continue
            money_unit = _MONEY_UNIT_RE.search(line)
            if money_unit:
                label = line[: money_unit.start()].strip()
                rows.append(
                    _row(
                        obs_date,
                        f"Groundwater protection, {label.lower()}, volume charge",
                        float(money_unit.group("price")),
                        money_unit.group("unit").lower(),
                        "04.4.3",
                        source_url,
                        "groundwater protection volume charge",
                        ts,
                    )
                )
            label = line.split("$", 1)[0].rsplit(" ", 1)[0].strip(" -")
            rows.append(
                _row(
                    obs_date,
                    f"Groundwater protection, {label.lower()}, service charge",
                    nums[-1],
                    "meter_month",
                    "04.4.3",
                    source_url,
                    "groundwater protection service charge per meter",
                    ts,
                )
            )

    return rows


def fetch_as_aspa_utility_rates(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    resp = session.get(_RATES_URL, timeout=30)
    resp.raise_for_status()

    urls = []
    for match in _PDF_HREF_RE.finditer(resp.text):
        url = urljoin(_RATES_URL, match.group("href"))
        if url not in urls:
            urls.append(url)

    by_hash: dict[str, dict] = {}
    for url in urls:
        try:
            pdf_resp = session.get(url, timeout=60)
            pdf_resp.raise_for_status()
            with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] PDF fetch/parse failed for %s: %s", _SOURCE_KEY, url, exc)
            continue

        obs_date = _month_from_text(text)
        if obs_date is None:
            logger.warning("[%s] no billing month parsed from %s", _SOURCE_KEY, url)
            continue
        if obs_date <= cutoff:
            continue
        for row in _parse_pdf(text, obs_date, url):
            by_hash[row["observation_hash"]] = row

    rows = sorted(
        by_hash.values(), key=lambda r: (r["observation_date"], r["item_name"])
    )
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
