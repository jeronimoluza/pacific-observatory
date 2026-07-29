#!/usr/bin/env python3
"""GDELT domains-by-country source for the known_aggregators populator.

GDELT publishes a flat lookup of every web domain it monitors, cross-
referenced to a country via mention affinity: one row per (domain,
country) with a mention count. Unlike the four HTML aggregators (each
has a per-country page to scrape), GDELT is a single CSV that we group
ourselves — a domain is assigned to the country where it is mentioned
most (argmax count), and within a country the domains are ranked by
that count so the genuine national outlets sort to the top.

Country codes are FIPS 10-4 (circa-2015); we crosswalk FIPS -> ISO3 and
then ISO3 -> our slug via src/configs/countries.yaml.

Dataset: "Mapping The Media: A Geographic Lookup Of GDELT's Sources
2015-2021" — https://blog.gdeltproject.org/mapping-the-media-a-geographic-lookup-of-gdelts-sources-2015-2021/
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import httpx

GDELT_CSV_URL = (
    "https://blog.gdeltproject.org/wp-content/uploads/"
    "2021-news-outlets-by-countrycode-2015-2021.csv"
)

# FIPS 10-4 country code -> ISO 3166-1 alpha-3. Two FIPS codes may map to
# one ISO3 (e.g. WE/GZ -> PSE); that is fine — domains from both are then
# unioned into the same slug downstream.
FIPS_TO_ISO3 = {
    "AF": "AFG",
    "AL": "ALB",
    "AG": "DZA",
    "AN": "AND",
    "AO": "AGO",
    "AC": "ATG",
    "AR": "ARG",
    "AM": "ARM",
    "AA": "ABW",
    "AS": "AUS",
    "AQ": "ASM",
    "AU": "AUT",
    "AJ": "AZE",
    "BF": "BHS",
    "BA": "BHR",
    "BG": "BGD",
    "BB": "BRB",
    "BO": "BLR",
    "BE": "BEL",
    "BH": "BLZ",
    "BN": "BEN",
    "BD": "BMU",
    "BT": "BTN",
    "BL": "BOL",
    "BK": "BIH",
    "BC": "BWA",
    "BR": "BRA",
    "BX": "BRN",
    "BU": "BGR",
    "UV": "BFA",
    "BM": "MMR",
    "BY": "BDI",
    "CB": "KHM",
    "CM": "CMR",
    "CA": "CAN",
    "CV": "CPV",
    "CJ": "CYM",
    "CT": "CAF",
    "CD": "TCD",
    "CI": "CHL",
    "CH": "CHN",
    "CO": "COL",
    "CN": "COM",
    "CF": "COG",
    "CG": "COD",
    "CW": "COK",
    "CS": "CRI",
    "IV": "CIV",
    "HR": "HRV",
    "CU": "CUB",
    "UC": "CUW",
    "CY": "CYP",
    "EZ": "CZE",
    "DA": "DNK",
    "DJ": "DJI",
    "DO": "DMA",
    "DR": "DOM",
    "EC": "ECU",
    "EG": "EGY",
    "ES": "SLV",
    "EK": "GNQ",
    "ER": "ERI",
    "EN": "EST",
    "WZ": "SWZ",
    "ET": "ETH",
    "FO": "FRO",
    "FA": "FRO",
    "FJ": "FJI",
    "FI": "FIN",
    "FR": "FRA",
    "FP": "PYF",
    "GB": "GAB",
    "GA": "GMB",
    "GG": "GEO",
    "GM": "DEU",
    "GH": "GHA",
    "GI": "GIB",
    "GR": "GRC",
    "GL": "GRL",
    "GJ": "GRD",
    "GQ": "GUM",
    "GT": "GTM",
    "GK": "GGY",
    "GV": "GIN",
    "PU": "GNB",
    "GY": "GUY",
    "HA": "HTI",
    "HO": "HND",
    "HK": "HKG",
    "HU": "HUN",
    "IC": "ISL",
    "IN": "IND",
    "ID": "IDN",
    "IR": "IRN",
    "IZ": "IRQ",
    "EI": "IRL",
    "IM": "IMN",
    "IS": "ISR",
    "IT": "ITA",
    "JM": "JAM",
    "JA": "JPN",
    "JE": "JEY",
    "JO": "JOR",
    "KZ": "KAZ",
    "KE": "KEN",
    "KR": "KIR",
    "KN": "PRK",
    "KS": "KOR",
    "KV": "XKX",
    "KU": "KWT",
    "KG": "KGZ",
    "LA": "LAO",
    "LG": "LVA",
    "LE": "LBN",
    "LT": "LSO",
    "LI": "LBR",
    "LY": "LBY",
    "LS": "LIE",
    "LH": "LTU",
    "LU": "LUX",
    "MC": "MAC",
    "MK": "MKD",
    "MA": "MDG",
    "MI": "MWI",
    "MY": "MYS",
    "MV": "MDV",
    "ML": "MLI",
    "MT": "MLT",
    "RM": "MHL",
    "MB": "MTQ",
    "MR": "MRT",
    "MP": "MUS",
    "MX": "MEX",
    "FM": "FSM",
    "MD": "MDA",
    "MN": "MCO",
    "MG": "MNG",
    "MJ": "MNE",
    "MO": "MAR",
    "MZ": "MOZ",
    "WA": "NAM",
    "NR": "NRU",
    "NP": "NPL",
    "NL": "NLD",
    "NC": "NCL",
    "NZ": "NZL",
    "NU": "NIC",
    "NG": "NER",
    "NI": "NGA",
    "NE": "NIU",
    "CQ": "MNP",
    "NO": "NOR",
    "MU": "OMN",
    "PK": "PAK",
    "PS": "PLW",
    "PM": "PAN",
    "PP": "PNG",
    "PA": "PRY",
    "PE": "PER",
    "RP": "PHL",
    "PL": "POL",
    "PO": "PRT",
    "RQ": "PRI",
    "QA": "QAT",
    "RO": "ROU",
    "RS": "RUS",
    "RW": "RWA",
    "RN": "MAF",
    "SC": "KNA",
    "ST": "LCA",
    "VC": "VCT",
    "WS": "WSM",
    "SM": "SMR",
    "TP": "STP",
    "SA": "SAU",
    "SG": "SEN",
    "RI": "SRB",
    "SE": "SYC",
    "SL": "SLE",
    "SN": "SGP",
    "NN": "SXM",
    "LO": "SVK",
    "SI": "SVN",
    "BP": "SLB",
    "SO": "SOM",
    "SF": "ZAF",
    "OD": "SSD",
    "SP": "ESP",
    "CE": "LKA",
    "SU": "SDN",
    "NS": "SUR",
    "SW": "SWE",
    "SZ": "CHE",
    "SY": "SYR",
    "TW": "TWN",
    "TI": "TJK",
    "TZ": "TZA",
    "TH": "THA",
    "TT": "TLS",
    "TO": "TGO",
    "TN": "TON",
    "TD": "TTO",
    "TS": "TUN",
    "TU": "TUR",
    "TX": "TKM",
    "TK": "TCA",
    "TV": "TUV",
    "UG": "UGA",
    "UP": "UKR",
    "AE": "ARE",
    "UK": "GBR",
    "US": "USA",
    "UY": "URY",
    "UZ": "UZB",
    "NH": "VUT",
    "VE": "VEN",
    "VM": "VNM",
    "VI": "VGB",
    "VQ": "VIR",
    "WE": "PSE",
    "GZ": "PSE",
    "YM": "YEM",
    "ZA": "ZMB",
    "ZI": "ZWE",
}


def harvest_gdelt_domains(cache_path: Path) -> dict[str, list[tuple[str, int]]]:
    """Download the GDELT CSV (cached) and return {FIPS: [(domain, count), ...]}.

    Each domain is argmax-assigned to the country with its highest mention
    count; within each country the list is sorted by count descending.
    """
    if not cache_path.exists() or cache_path.stat().st_size == 0:
        print(f"[gdelt] downloading {GDELT_CSV_URL}")
        with httpx.Client(timeout=120.0, follow_redirects=True) as cli:
            r = cli.get(GDELT_CSV_URL)
            r.raise_for_status()
            cache_path.write_bytes(r.content)
    else:
        print(f"[gdelt] using cached csv {cache_path}")

    best: dict[str, tuple[str, int]] = {}
    with open(cache_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)  # header: domain,countrycode,cnt
        for row in reader:
            if len(row) != 3:
                continue
            domain, cc, cnt = row
            try:
                c = int(cnt)
            except ValueError:
                continue
            if domain not in best or c > best[domain][1]:
                best[domain] = (cc, c)

    by_fips: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for domain, (cc, c) in best.items():
        by_fips[cc].append((domain, c))
    for cc in by_fips:
        by_fips[cc].sort(key=lambda t: -t[1])
    print(f"[gdelt] {len(best)} domains across {len(by_fips)} FIPS codes")
    return by_fips


def build_iso3_to_fips() -> dict[str, list[str]]:
    """Reverse the crosswalk: ISO3 -> [FIPS, ...] (usually one, sometimes two)."""
    out: dict[str, list[str]] = defaultdict(list)
    for fips, iso3 in FIPS_TO_ISO3.items():
        out[iso3].append(fips)
    return out


def gdelt_block_for_country(
    iso3: str,
    iso3_to_fips: dict[str, list[str]],
    by_fips: dict[str, list[tuple[str, int]]],
    is_ignored,
    cap: int,
) -> tuple[str | None, list[tuple[str, str]]]:
    """Return (section_annotation, [(domain, url), ...]) for one country.

    section_annotation is the string printed after '### gdelt — ' in the
    region file; it carries the dataset URL plus the visible truncation
    count so the cap is never silent. Returns (None, []) if the country is
    absent from GDELT or has no ISO3.
    """
    fips_codes = iso3_to_fips.get(iso3, [])
    if not iso3 or not fips_codes:
        return None, []

    merged: list[tuple[str, int]] = []
    for fips in fips_codes:
        merged.extend(by_fips.get(fips, []))
    merged.sort(key=lambda t: -t[1])

    kept: list[tuple[str, str]] = []
    seen: set[str] = set()
    for domain, _count in merged:
        d = domain.strip().lower()
        if not d or d in seen:
            continue
        url = f"https://{d}/"
        if is_ignored(url):
            continue
        seen.add(d)
        kept.append((d, url))

    total = len(kept)
    if total == 0:
        return None, []

    if cap and total > cap:
        annotation = (
            f"{GDELT_CSV_URL} (top {cap} of {total} by GDELT monitoring volume)"
        )
        kept = kept[:cap]
    else:
        annotation = f"{GDELT_CSV_URL} ({total} domains by GDELT monitoring volume)"
    return annotation, kept


# ---------- merge into existing region files ------------------------

_COUNTRY_SPLIT = re.compile(r"(?m)^(?=## )")
_EXISTING_GDELT = re.compile(r"(?ms)^### gdelt — .*?(?=^### |\Z)")


def render_gdelt_section(annotation: str | None, outlets: list[tuple[str, str]]) -> str:
    """Render a single '### gdelt' markdown section (trailing blank line)."""
    header = f"### gdelt — {annotation}" if annotation else "### gdelt — (not listed)"
    lines = [header]
    if outlets:
        lines.extend(f"- {name} — {url}" for name, url in outlets)
    else:
        lines.append("- (no entries)")
    lines.append("")
    return "\n".join(lines)


def inject_gdelt_into_text(text: str, resolve) -> str:
    """Splice a fresh '### gdelt' section into each country block of a region file.

    `resolve(slug) -> (annotation, outlets)`. Only the gdelt section is touched;
    the four existing aggregator sections are left byte-for-byte. Idempotent —
    any pre-existing gdelt section is replaced.
    """
    parts = _COUNTRY_SPLIT.split(text)
    out = [parts[0]]
    for block in parts[1:]:
        first_line = block.split("\n", 1)[0]
        m = re.match(r"^## (\S+) ", first_line)
        slug = m.group(1) if m else None
        block = _EXISTING_GDELT.sub("", block)
        annotation, outlets = resolve(slug) if slug else (None, [])
        block = block.rstrip("\n") + "\n\n" + render_gdelt_section(annotation, outlets)
        out.append(block.rstrip("\n") + "\n\n")
    return "".join(out)
