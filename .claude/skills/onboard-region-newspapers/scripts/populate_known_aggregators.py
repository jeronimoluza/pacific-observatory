#!/usr/bin/env python3
"""One-shot populator for references/known_aggregators/<region>.md.

Fetches per-country pages from four online-newspaper aggregators and
writes one markdown file per region containing the extracted outlet
lists. Used by the /onboard-region-newspapers skill at runtime as a
static seed instead of refetching aggregator homepages every run.

Aggregators:
    - w3newspapers.com       (Playwright — JS-rendered)
    - onlinenewspapers.com   (httpx)
    - allyoucanread.com      (httpx)
    - abyznewslinks.com      (httpx — pre-classified by media type;
                              IN+NP sections only)

Outputs (default): ~/.claude/skills/onboard-region-newspapers/
                   references/known_aggregators/<region>.md

Usage:
    poetry run python populate_known_aggregators.py \\
        --regions <repo>/src/configs/regions.yaml \\
        --countries <repo>/src/configs/countries.yaml \\
        --out ~/.claude/skills/onboard-region-newspapers/references/known_aggregators/
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
HTTP_HEADERS = {"User-Agent": UA}
HTTP_TIMEOUT = 25.0

ONLINE_REGIONAL_SITEMAPS = [
    "https://onlinenewspapers.com/sitemap/asia.shtml",
    "https://onlinenewspapers.com/sitemap/africa.shtml",
    "https://onlinenewspapers.com/sitemap/americas.shtml",
    "https://onlinenewspapers.com/sitemap/europe.shtml",
    "https://onlinenewspapers.com/sitemap/north-america.shtml",
    "https://onlinenewspapers.com/sitemap/canada-by-province.shtml",
]

ALLYOUCANREAD_INDEX = "https://www.allyoucanread.com/newspapers/"
W3NEWSPAPERS_HOMEPAGE = "https://www.w3newspapers.com/"
ABYZ_BASE = "http://www.abyznewslinks.com/"
ABYZ_ALL_COUNTRIES = "http://www.abyznewslinks.com/allco.htm"
# Site-nav / non-country pages on abyznewslinks.com to skip when
# parsing the all-countries index.
ABYZ_NON_COUNTRY_PAGES = {
    "seara.htm",
    "admod.htm",
    "resou.htm",
    "priva.htm",
    "about.htm",
    "contc.htm",
    "allco.htm",
    "inter.htm",
    "espan.htm",
    "united_nations.htm",
    "european_union.htm",
    "asia_pacific.htm",
    "latin_america.htm",
    "british_caribbean.htm",
    "dutch_caribbean.htm",
    "french_caribbean.htm",
}

IGNORE_DOMAIN_PATTERNS = [
    re.compile(r"(^|\.)wikipedia\.org$", re.I),
    re.compile(r"(^|\.)wikimedia\.org$", re.I),
    re.compile(r"(^|\.)bbc\.co\.uk$", re.I),
    re.compile(r"(^|\.)bbc\.com$", re.I),
    re.compile(r"(^|\.)cia\.gov$", re.I),
    re.compile(r"(^|\.)reuters\.com$", re.I),
    re.compile(r"(^|\.)afp\.com$", re.I),
    re.compile(r"(^|\.)aljazeera\.(com|net)$", re.I),
    re.compile(r"(^|\.)france24\.com$", re.I),
    re.compile(r"(^|\.)rfi\.(fr|com)$", re.I),
    re.compile(r"(^|\.)voanews\.com$", re.I),
    re.compile(r"(^|\.)dw\.com$", re.I),
    re.compile(r"(^|\.)cnn\.com$", re.I),
    re.compile(r"(^|\.)bloomberg\.com$", re.I),
    re.compile(r"(^|\.)apnews\.com$", re.I),
    re.compile(r"(^|\.)nytimes\.com$", re.I),
    re.compile(r"(^|\.)washingtonpost\.com$", re.I),
    re.compile(r"(^|\.)theguardian\.com$", re.I),
    re.compile(r"(^|\.)facebook\.com$", re.I),
    re.compile(r"(^|\.)twitter\.com$", re.I),
    re.compile(r"(^|\.)x\.com$", re.I),
    re.compile(r"(^|\.)youtube\.com$", re.I),
    re.compile(r"(^|\.)instagram\.com$", re.I),
    re.compile(r"(^|\.)linkedin\.com$", re.I),
    re.compile(r"(^|\.)pinterest\.com$", re.I),
    re.compile(r"(^|\.)tumblr\.com$", re.I),
    re.compile(r"(^|\.)t\.me$", re.I),
    re.compile(r"(^|\.)whatsapp\.com$", re.I),
    re.compile(r"(^|\.)telegram\.org$", re.I),
    re.compile(r"(^|\.)google\.com$", re.I),
    re.compile(r"(^|\.)googletagmanager\.com$", re.I),
    re.compile(r"(^|\.)gstatic\.com$", re.I),
    re.compile(r"(^|\.)w3newspapers\.com$", re.I),
    re.compile(r"(^|\.)onlinenewspapers\.com$", re.I),
    re.compile(r"(^|\.)allyoucanread\.com$", re.I),
    re.compile(r"(^|\.)abyznewslinks\.com$", re.I),
]

IGNORE_PATH_FRAGMENTS = [
    "wiki/",
    "factbook",
    "country-profiles",
    "country_profiles",
    "/news/world-",
]

# Aliases: normalized aggregator country name → our slug
# Use these to bridge name-mismatches between aggregator listings and our slugs.
NAME_ALIASES = {
    # w3newspapers / onlinenewspapers / allyoucanread variants
    "cape verde": "cabo_verde",
    "ivory coast": "cote_divoire",
    "cote d ivoire": "cote_divoire",
    "cote divoire": "cote_divoire",
    "cote d'ivoire": "cote_divoire",
    "myanmar burma": "myanmar",
    "burma": "myanmar",
    "burma myanmar": "myanmar",
    "korea south": "south_korea",
    "south korea": "south_korea",
    "korea north": "korea_dem_peoples_rep",
    "north korea": "korea_dem_peoples_rep",
    "democratic peoples republic of korea": "korea_dem_peoples_rep",
    "lao": "lao_pdr",
    "laos": "lao_pdr",
    "lao pdr": "lao_pdr",
    "macau": "macao_sar_china",
    "macao": "macao_sar_china",
    "hong kong": "hong_kong_sar_china",
    "taiwan": "taiwan_china",
    "russia": "russian_federation",
    "russian federation": "russian_federation",
    "kyrgyzstan": "kyrgyz_republic",
    "kyrgyz republic": "kyrgyz_republic",
    "slovakia": "slovak_republic",
    "slovak republic": "slovak_republic",
    "czechia": "czech_republic",
    "czech republic": "czech_republic",
    "macedonia": "north_macedonia",
    "north macedonia": "north_macedonia",
    "fyrom": "north_macedonia",
    "republic of macedonia": "north_macedonia",
    "turkey": "turkiye",
    "turkiye": "turkiye",
    "egypt": "egypt",
    "iran": "iran",
    "syrian arab republic": "syria",
    "syria": "syria",
    "yemen arab republic": "yemen",
    "palestine": "west_bank_and_gaza",
    "palestinian territory": "west_bank_and_gaza",
    "west bank": "west_bank_and_gaza",
    "gaza": "west_bank_and_gaza",
    "tanzania": "tanzania",
    "united republic of tanzania": "tanzania",
    "republic of the congo": "congo_rep",
    "congo": "congo_rep",
    "congo brazzaville": "congo_rep",
    "republic of congo": "congo_rep",
    "congo republic of": "congo_rep",
    "democratic republic of the congo": "congo_dem_rep",
    "democratic republic of congo": "congo_dem_rep",
    "drc": "congo_dem_rep",
    "dr congo": "congo_dem_rep",
    "congo kinshasa": "congo_dem_rep",
    "congo democratic republic": "congo_dem_rep",
    "swaziland": "eswatini",
    "eswatini": "eswatini",
    "venezuela": "venezuela_rb",
    "the bahamas": "bahamas_the",
    "bahamas": "bahamas_the",
    "antigua barbuda": "antigua_and_barbuda",
    "antigua and barbuda": "antigua_and_barbuda",
    "saint kitts and nevis": "st_kitts_and_nevis",
    "st kitts nevis": "st_kitts_and_nevis",
    "st kitts and nevis": "st_kitts_and_nevis",
    "saint lucia": "st_lucia",
    "st lucia": "st_lucia",
    "saint vincent and the grenadines": "st_vincent_and_the_grenadines",
    "st vincent grenadines": "st_vincent_and_the_grenadines",
    "saint vincent and grenadines": "st_vincent_and_the_grenadines",
    "saint martin": "st_martin_french_part",
    "st martin": "st_martin_french_part",
    "sint maarten": "sint_maarten_dutch_part",
    "trinidad and tobago": "trinidad_and_tobago",
    "trinidad tobago": "trinidad_and_tobago",
    "turks and caicos": "turks_and_caicos_islands",
    "turks caicos": "turks_and_caicos_islands",
    "us virgin islands": "virgin_islands_us",
    "virgin islands us": "virgin_islands_us",
    "united states virgin islands": "virgin_islands_us",
    "british virgin islands": "british_virgin_islands",
    "puerto rico": "puerto_rico",
    "curacao": "curacao",
    "curaçao": "curacao",
    "bosnia herzegovina": "bosnia_and_herzegovina",
    "bosnia and herzegovina": "bosnia_and_herzegovina",
    "moldova": "moldova",
    "republic of moldova": "moldova",
    "vietnam": "vietnam",
    "viet nam": "vietnam",
    "guinea bissau": "guinea_bissau",
    "guinea-bissau": "guinea_bissau",
    "sao tome principe": "sao_tome_and_principe",
    "sao tome and principe": "sao_tome_and_principe",
    "central african rep": "central_african_republic",
    "central african republic": "central_african_republic",
    "central africa republic": "central_african_republic",
    "south sudan": "south_sudan",
    "sudan south": "south_sudan",
    "timor leste": "timor_leste",
    "east timor": "timor_leste",
    "timor": "timor_leste",
    "papua new guinea": "papua_new_guinea",
    "marshall islands": "marshall_islands",
    "solomon islands": "solomon_islands",
    "cook islands": "cook_islands",  # not in our list but harmless
    "federated states of micronesia": "micronesia_fed_sts",
    "micronesia": "micronesia_fed_sts",
    "northern mariana islands": "northern_mariana_islands",
    "new caledonia": "new_caledonia",
    "french polynesia": "french_polynesia",
    "american samoa": "american_samoa",
    "new zealand": "new_zealand",
    "isle of man": "isle_of_man",
    "channel islands": "channel_islands",
    "san marino": "san_marino",
    "saint helena": None,
    "faroe islands": "faroe_islands",
    "faeroe islands": "faroe_islands",
    "greenland": "greenland",
    "gibraltar": "gibraltar",
    "monaco": "monaco",
    "liechtenstein": "liechtenstein",
    "luxembourg": "luxembourg",
    "malta": "malta",
    "andorra": "andorra",
    "vatican city": None,
    "saudi arabia": "saudi_arabia",
    "united arab emirates": "united_arab_emirates",
    "uae": "united_arab_emirates",
    "el salvador": "el_salvador",
    "costa rica": "costa_rica",
    "dominican republic": "dominican_republic",
    "burkina faso": "burkina_faso",
    "sierra leone": "sierra_leone",
    "south africa": "south_africa",
    "western sahara": None,
    "south georgia": None,
    "ascension island": None,
    "antarctica": None,
    "us state newspapers": None,
    "british indian ocean territory": None,
    "saint barthelemy": None,
    "saint pierre and miquelon": None,
}


def normalize_name(name: str) -> str:
    """Normalize a country name for fuzzy matching."""
    s = name.lower().strip()
    s = re.sub(r"[’']", " ", s)  # apostrophes → space
    s = re.sub(r"[&,/\-]", " ", s)
    s = re.sub(r"\bnewspapers\b", "", s)
    s = re.sub(r"\bonline\b", "", s)
    s = re.sub(r"\bnews\b", "", s)
    s = re.sub(r"\bthe\b", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def slug_match(slug: str, normalized: str) -> bool:
    """Match an aggregator-normalized name to our country slug."""
    slug_norm = slug.replace("_", " ")
    if normalized == slug_norm:
        return True
    return NAME_ALIASES.get(normalized) == slug


def domain_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def is_ignored(url: str) -> bool:
    d = domain_of(url)
    if not d:
        return True
    for pat in IGNORE_DOMAIN_PATTERNS:
        if pat.search(d):
            return True
    low = url.lower()
    for frag in IGNORE_PATH_FRAGMENTS:
        if frag in low:
            return True
    return False


def extract_outlets(html: str, base_host: str) -> list[tuple[str, str]]:
    """Extract (name, url) pairs from a per-country listing page."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str]] = []
    seen_urls = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href").strip()
        text = a.get_text(strip=True)
        if not href.startswith("http"):
            continue
        if not text or len(text) < 2 or len(text) > 80:
            continue
        host = domain_of(href)
        if host == base_host or host.endswith("." + base_host):
            continue
        if is_ignored(href):
            continue
        # canonicalize URL by host (avoid duplicates that differ only in path/scheme)
        norm_url = f"{urlparse(href).scheme}://{host}/"
        if norm_url in seen_urls:
            continue
        seen_urls.add(norm_url)
        results.append((text, href))
    return results


# ---------- aggregator harvesters -----------------------------------


def harvest_w3newspapers_index() -> dict[str, str]:
    """Map of normalized country name → per-country URL."""
    print("[w3newspapers] launching playwright")
    out: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)
        try:
            page.goto(
                W3NEWSPAPERS_HOMEPAGE, wait_until="domcontentloaded", timeout=30000
            )
            html = page.content()
        finally:
            browser.close()
    soup = BeautifulSoup(html, "html.parser")
    # The homepage lists every country once. Path is /<slug>/.
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        text = a.get_text(strip=True)
        if not text or len(text) > 50:
            continue
        m = re.match(r"^/([a-z][a-z0-9\-]+)/$", href)
        if not m:
            continue
        norm = normalize_name(text)
        if not norm:
            continue
        full = f"https://www.w3newspapers.com{href}"
        out.setdefault(norm, full)
    print(f"[w3newspapers] index: {len(out)} entries")
    return out


def harvest_onlinenewspapers_index() -> dict[str, str]:
    out: dict[str, str] = {}
    with httpx.Client(
        headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT, follow_redirects=True
    ) as cli:
        for url in ONLINE_REGIONAL_SITEMAPS:
            try:
                r = cli.get(url)
            except Exception as e:
                print(f"[onlinenewspapers] sitemap err {url}: {e}")
                continue
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href")
                text = a.get_text(strip=True)
                if not href.endswith(".shtml") or "sitemap" in href:
                    continue
                if not text or len(text) > 60:
                    continue
                full = (
                    href
                    if href.startswith("http")
                    else f"https://onlinenewspapers.com/{href.lstrip('/')}"
                )
                norm = normalize_name(text)
                if not norm:
                    continue
                out.setdefault(norm, full)
    print(f"[onlinenewspapers] index: {len(out)} entries")
    return out


def harvest_abyz_index() -> dict[str, str]:
    """Map normalized country name → per-country .htm URL on abyznewslinks.com.

    Discovery via the all-countries index page (one fetch). Skips known
    site-nav and "X Regional" / continent-level aggregator pages.
    """
    out: dict[str, str] = {}
    with httpx.Client(
        headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT, follow_redirects=True
    ) as cli:
        r = cli.get(ABYZ_ALL_COUNTRIES)
        if r.status_code != 200:
            print(f"[abyz] index status {r.status_code}")
            return out
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href").strip()
            text = a.get_text(strip=True)
            if not re.match(r"^[a-z_]+\.htm$", href):
                continue
            if href in ABYZ_NON_COUNTRY_PAGES:
                continue
            # Skip regional-aggregator pages — they list cross-country
            # wires, not a specific country's outlets. Filter on the
            # link TEXT not the href: "nkore.htm" / "skore.htm" end in
            # "re.htm" but are real countries (North/South Korea).
            if not text or len(text) > 60:
                continue
            if "regional" in text.lower():
                continue
            if "regional" in href:
                continue
            norm = normalize_name(text)
            if not norm:
                continue
            # Also register the parenthesized alias as a separate key,
            # e.g. "Cabo Verde (Cape Verde)" → both "cabo verde" and
            # "cape verde" point to the same page.
            full = f"{ABYZ_BASE}{href}"
            out.setdefault(norm, full)
            paren = re.search(r"\(([^)]+)\)", text)
            if paren:
                alt = normalize_name(paren.group(1))
                if alt and alt != norm:
                    out.setdefault(alt, full)
                # Also register the part BEFORE the parenthesis on its own.
                bare = normalize_name(text.split("(")[0])
                if bare and bare != norm:
                    out.setdefault(bare, full)
    print(f"[abyz] index: {len(out)} entries")
    return out


def extract_abyz_outlets(html: str) -> list[tuple[str, str]]:
    """Extract (name, url) pairs from an abyz country page.

    Filters to **Internet** + **Newspaper** sections only — skipping
    Broadcast (TV/radio), Press Agency (wire services), and Magazine.
    Section banners look like `<b>{Country} - Internet News Media</b>`;
    we walk <b> + <a> elements in document order, toggling a "keep"
    flag based on the most recent banner.
    """
    soup = BeautifulSoup(html, "html.parser")
    keep_section_re = re.compile(r"-\s*(Internet|Newspaper)\s+News Media", re.I)
    results: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    current_keep = False
    for elem in soup.find_all(["b", "a"]):
        if elem.name == "b":
            txt = elem.get_text(" ", strip=True)
            # Only act on banner-style headings ("X News Media"); ignore
            # the legend boxes ("Media Type", "Language", etc.) and city
            # sub-headers ("Coast", "Nairobi").
            if "News Media" in txt:
                current_keep = bool(keep_section_re.search(txt))
            continue
        if not current_keep:
            continue
        href = (elem.get("href") or "").strip()
        text = elem.get_text(strip=True)
        if not href.startswith("http") or not text:
            continue
        if len(text) < 2 or len(text) > 80:
            continue
        if is_ignored(href):
            continue
        host = domain_of(href)
        if not host:
            continue
        norm_url = f"{urlparse(href).scheme}://{host}/"
        if norm_url in seen_urls:
            continue
        seen_urls.add(norm_url)
        results.append((text, href))
    return results


def harvest_allyoucanread_index() -> dict[str, str]:
    out: dict[str, str] = {}
    with httpx.Client(
        headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT, follow_redirects=True
    ) as cli:
        r = cli.get(ALLYOUCANREAD_INDEX)
        if r.status_code != 200:
            print(f"[allyoucanread] index status {r.status_code}")
            return out
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            text = a.get_text(strip=True)
            if not href.startswith("/") or not href.endswith("-newspapers/"):
                continue
            if not text or len(text) > 50:
                continue
            # Skip the 6 region links
            if text.lower().strip() in {
                "africa",
                "asia",
                "europe",
                "north america",
                "south america",
                "australia & pacific",
            }:
                continue
            full = f"https://www.allyoucanread.com{href}"
            norm = normalize_name(text)
            if not norm:
                continue
            out.setdefault(norm, full)
    print(f"[allyoucanread] index: {len(out)} entries")
    return out


# ---------- per-country fetch ---------------------------------------


def fetch_w3_country(url: str, _shared_browser=None) -> str | None:
    """Fetch a w3newspapers country page using Playwright."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                html = page.content()
            finally:
                browser.close()
        return html
    except Exception as e:
        print(f"  [w3] err {url}: {e}")
        return None


def fetch_http(url: str, cli: httpx.Client) -> str | None:
    try:
        r = cli.get(url)
        if r.status_code == 200:
            return r.text
        print(f"  [http] {r.status_code} {url}")
    except Exception as e:
        print(f"  [http] err {url}: {e}")
    return None


# ---------- main pipeline -------------------------------------------


def load_topology(regions_path: Path, countries_path: Path):
    with open(regions_path) as f:
        regions = yaml.safe_load(f)
    with open(countries_path) as f:
        countries = yaml.safe_load(f)
    rows = []
    for region_key, region_data in regions.items():
        for sub_key, sub_data in region_data.get("subregions", {}).items():
            for slug in sub_data.get("countries", []):
                cdata = countries.get(slug, {})
                display = cdata.get("name", slug.replace("_", " ").title())
                rows.append((region_key, sub_key, slug, display))
    return rows


def lookup(slug: str, display: str, index: dict[str, str]) -> str | None:
    """Find aggregator URL for a country."""
    norm_slug = slug.replace("_", " ")
    norm_display = normalize_name(display)
    # 1. exact match on normalized slug
    if norm_slug in index:
        return index[norm_slug]
    # 2. exact match on normalized display name
    if norm_display in index:
        return index[norm_display]
    # 3. alias map (any aggregator key whose alias maps to our slug)
    for aggr_norm, url in index.items():
        if NAME_ALIASES.get(aggr_norm) == slug:
            return url
    # 4. relaxed: drop trailing words like "republic", "the"
    relaxed = re.sub(
        r"\b(republic|democratic|peoples?|the|of|and|sar)\b", "", norm_slug
    ).strip()
    relaxed = re.sub(r"\s+", " ", relaxed)
    if relaxed and relaxed in index:
        return index[relaxed]
    relaxed_d = re.sub(
        r"\b(republic|democratic|peoples?|the|of|and|sar)\b", "", norm_display
    ).strip()
    relaxed_d = re.sub(r"\s+", " ", relaxed_d)
    if relaxed_d and relaxed_d in index:
        return index[relaxed_d]
    return None


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


AGGREGATORS = ("w3newspapers", "onlinenewspapers", "allyoucanread", "abyznewslinks")


def write_region_file(
    out_dir: Path,
    region: str,
    region_name: str,
    country_blocks: list[
        tuple[str, str, str, dict[str, tuple[str, list[tuple[str, str]]]]]
    ],
):
    """country_blocks: (subregion, slug, display, {aggregator: (page_url, [(name, url), ...])})"""
    lines = [
        f"# Known Online-Newspaper Aggregators — {region_name} (`{region}`)",
        "",
        "Pre-extracted per-country newspaper lists from four online-newspaper",
        "aggregators. Used by `/onboard-region-newspapers` step 2a as a static",
        "seed instead of refetching aggregator homepages every run.",
        "",
        "See `references/known_aggregators/README.md` for the ignore rules and",
        "the populator script that generated this file.",
        "",
        "---",
        "",
    ]
    for sub, slug, display, aggregators in country_blocks:
        lines.append(f"## {slug} ({sub}) — {display}")
        lines.append("")
        for agg in AGGREGATORS:
            page_url, outlets = aggregators.get(agg, (None, []))
            if page_url:
                lines.append(f"### {agg} — {page_url}")
            else:
                lines.append(f"### {agg} — (not listed)")
            if outlets:
                for name, url in outlets:
                    lines.append(f"- {name} — {url}")
            else:
                lines.append("- (no entries)")
            lines.append("")
    (out_dir / f"{region}.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regions", required=True, type=Path)
    parser.add_argument("--countries", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If >0, process only the first N countries (for testing)",
    )
    parser.add_argument(
        "--skip-w3",
        action="store_true",
        help="Skip w3newspapers (Playwright) — useful for fast iteration",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    print("[load] topology")
    topology = load_topology(args.regions, args.countries)
    print(f"  countries: {len(topology)}")
    if args.limit:
        topology = topology[: args.limit]

    # Harvest indexes
    if not args.skip_w3:
        w3_idx = harvest_w3newspapers_index()
    else:
        w3_idx = {}
    online_idx = harvest_onlinenewspapers_index()
    ayr_idx = harvest_allyoucanread_index()
    abyz_idx = harvest_abyz_index()

    # Resolve per-country URLs
    print("[resolve] mapping our slugs → aggregator URLs")
    resolved: dict[str, dict[str, str | None]] = {}
    for region, sub, slug, display in topology:
        resolved[slug] = {
            "w3newspapers": lookup(slug, display, w3_idx),
            "onlinenewspapers": lookup(slug, display, online_idx),
            "allyoucanread": lookup(slug, display, ayr_idx),
            "abyznewslinks": lookup(slug, display, abyz_idx),
        }

    miss_w3 = sum(1 for r in resolved.values() if not r["w3newspapers"])
    miss_on = sum(1 for r in resolved.values() if not r["onlinenewspapers"])
    miss_ay = sum(1 for r in resolved.values() if not r["allyoucanread"])
    miss_ab = sum(1 for r in resolved.values() if not r["abyznewslinks"])
    print(f"  unresolved: w3={miss_w3} online={miss_on} ayr={miss_ay} abyz={miss_ab}")

    # Fetch per-country pages — w3 via shared browser, others via httpx
    print("[fetch] per-country pages")
    pages: dict[str, dict[str, tuple[str, list[tuple[str, str]]]]] = {}

    # Single httpx client for the two HTTP aggregators
    http_cli = httpx.Client(
        headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT, follow_redirects=True
    )

    # Single playwright browser for w3
    pw = sync_playwright().start() if not args.skip_w3 else None
    w3_browser = pw.chromium.launch(headless=True) if pw else None
    w3_ctx = w3_browser.new_context(user_agent=UA) if w3_browser else None

    try:
        for i, (region, sub, slug, display) in enumerate(topology, 1):
            urls = resolved[slug]
            country_pages: dict[str, tuple[str, list[tuple[str, str]]]] = {}
            print(f"[{i}/{len(topology)}] {slug} ({region}/{sub})")

            # w3newspapers
            if urls["w3newspapers"] and w3_ctx:
                page = w3_ctx.new_page()
                try:
                    try:
                        page.goto(
                            urls["w3newspapers"],
                            wait_until="domcontentloaded",
                            timeout=30000,
                        )
                        html = page.content()
                    except Exception as e:
                        print(f"  [w3] err: {e}")
                        html = None
                finally:
                    page.close()
                if html:
                    outlets = extract_outlets(html, "w3newspapers.com")
                    country_pages["w3newspapers"] = (urls["w3newspapers"], outlets)
                    print(f"  [w3] {len(outlets)} outlets")

            # onlinenewspapers
            if urls["onlinenewspapers"]:
                html = fetch_http(urls["onlinenewspapers"], http_cli)
                if html:
                    outlets = extract_outlets(html, "onlinenewspapers.com")
                    country_pages["onlinenewspapers"] = (
                        urls["onlinenewspapers"],
                        outlets,
                    )
                    print(f"  [online] {len(outlets)} outlets")

            # allyoucanread
            if urls["allyoucanread"]:
                html = fetch_http(urls["allyoucanread"], http_cli)
                if html:
                    outlets = extract_outlets(html, "allyoucanread.com")
                    country_pages["allyoucanread"] = (urls["allyoucanread"], outlets)
                    print(f"  [ayr] {len(outlets)} outlets")

            # abyznewslinks
            if urls["abyznewslinks"]:
                html = fetch_http(urls["abyznewslinks"], http_cli)
                if html:
                    outlets = extract_abyz_outlets(html)
                    country_pages["abyznewslinks"] = (urls["abyznewslinks"], outlets)
                    print(f"  [abyz] {len(outlets)} outlets")

            pages[slug] = country_pages
            time.sleep(0.4)
    finally:
        http_cli.close()
        if w3_browser:
            w3_browser.close()
        if pw:
            pw.stop()

    # Group by region and write files
    print("[write] per-region files")
    by_region: dict[str, list] = defaultdict(list)
    region_names: dict[str, str] = {}
    with open(args.regions) as f:
        regions_yaml = yaml.safe_load(f)
    for r_key, r_data in regions_yaml.items():
        region_names[r_key] = r_data.get("name", r_key)

    for region, sub, slug, display in topology:
        country_pages = pages.get(slug, {})
        # Build aggregator dict with default empties for any missing aggregator
        aggregators = {}
        for agg in AGGREGATORS:
            if agg in country_pages:
                aggregators[agg] = country_pages[agg]
            else:
                # No URL resolved or fetch failed → preserve "(not listed)" in output
                aggregators[agg] = (resolved[slug].get(agg), [])
        by_region[region].append((sub, slug, display, aggregators))

    for region, blocks in by_region.items():
        write_region_file(args.out, region, region_names.get(region, region), blocks)
        print(f"  wrote {region}.md ({len(blocks)} countries)")

    print("[done]")


if __name__ == "__main__":
    sys.exit(main() or 0)
