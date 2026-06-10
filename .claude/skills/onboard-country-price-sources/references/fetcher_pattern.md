# Fetcher pattern — Python fetchers for prices

This doc has three jobs:

1. **Contract** — what every fetcher MUST satisfy. Mandatory.
2. **Helpers** — a small toolbox under `src/prices/fetchers/utils.py`. Optional; use when convenient.
3. **Worked examples** — concrete code from real sources. Read what's relevant; do not treat as fill-in-the-blank templates.

Two things this doc deliberately does **not** do:

- It does not prescribe a uniform skeleton (private-constant naming, fixed module layout). Prices fetchers genuinely differ in shape; forcing them into one mold hides per-source decisions.
- It does not duplicate scaffolding decisions that already live in the YAML manifest (`scaffolding`, `extraction_pattern`, `analytical_role`, `coicop_classification`). The fetcher implementation reads from the YAML's facts; it doesn't re-encode them.

---

## 1. Contract

### Function signature

```python
def fetch_<source_key>(cutoff: date) -> pd.DataFrame | None
```

For regional aggregators (bucket 2) the public name is `fetch_<cc>_<source_key>` (e.g. `fetch_sg_shopee`).

### Idempotence

Skip any observation whose `observation_date <= cutoff`. The collect layer passes the high-water mark from the source's existing output file; on first run it passes the YAML's `fallback_date`. The fetcher does not maintain its own cursor.

### Return value

- Empty or no new data → return `None`. Do not return an empty DataFrame.
- Otherwise → return a DataFrame whose columns match one of the two row schemas in §2.

### Schema choice

The YAML's `analytical_role` field determines which schema the fetcher emits:

| `analytical_role` | Schema |
|---|---|
| `retailer_sku` (type-A spiders; not relevant for Python fetchers) | PriceObservation |
| `official_avg` | PriceObservation |
| `tariff` | PriceObservation |
| `cpi_benchmark` | IndexObservation |
| `aggregate_proxy` (commodity benchmarks like Pink Sheet) | PriceObservation |

One fetcher emits exactly one schema. If a single source publishes both averaged prices and CPI indexes, it is two fetchers with two YAMLs.

### Determinism

`observation_hash` is set LAST, after every identifying field is populated. Hashing before populating produces duplicate rows on re-run. Use `make_hash(row, identifying_fields)` from the helpers, with a module-private `_IDENT` list naming the columns that identify a row.

### COICOP tagging ownership

The YAML's `coicop_classification` field declares who tags COICOP for this source:

| `coicop_classification` | Fetcher behavior |
|---|---|
| `deferred_gemini` | Fetcher does NOT populate `coicop_code`. Downstream `src/cpi/coicopping/` (Gemini-based) handles it. Typical for retailer SKU spiders and stats-office tables with long free-text item lists. |
| `source_curated` | Fetcher populates `coicop_code` from a module-level `_COICOP_MAP` keyed by commodity / item / plan name. The skill author writes this map once during onboarding. Typical for fuel, electricity, water, telco, real-estate, tariff schedules — sources whose domain unambiguously determines COICOP. |
| `publisher_labeled` | Fetcher reads `coicop_code` from labels the publisher itself emits. May need a language-translation map (e.g. Bahasa → COICOP codes for BPS Indonesia). Typical for CPI indexes. |

Rows that should carry a `coicop_code` but for which the map fails to resolve MUST be dropped with a logged warning. A null `coicop_code` row that should have been populated is pollution masquerading as coverage.

---

## 2. Row schemas

### PriceObservation

Used for: retailer SKU spiders (downstream — see `references/spider_templates.md`), official price-tracker APIs, stats-office averages, tariff schedules, real-estate listings, aggregate-proxy series (Pink Sheet etc.).

| Column | Required | Notes |
|---|---|---|
| `observation_date` | yes | ISO `YYYY-MM-DD`. The date the price applies to, not the fetch time. |
| `period_kind` | yes | One of `snapshot`, `weekly_avg`, `monthly_avg`, `annual_avg`, `effective_from`. Distinguishes commensurate vs aggregated observations. |
| `country` | yes | Matches `countries.yaml` (e.g. `"Indonesia"`, `"Singapore"`). Bucket-3 fetchers use `"Global"` or `"EAP"`. |
| `source_key` | yes | Matches the YAML manifest's `source_key:`. |
| `item_name` | yes | Stable, human-readable identifier for what was priced (e.g. `"Petrol RON95"`, `"Bread, white, sliced, 500g"`). |
| `price_local` | yes | Numeric. Bounds-check before emitting; currency-display shorthand (IDR `"12,90"` meaning `12,900`) is the most common 10×/100× error source. |
| `currency` | yes | ISO 4217 code (`"IDR"`, `"SGD"`, `"FJD"`). Never parse from price-display symbol — set from `countries.yaml`. |
| `unit` | yes | The physical unit `price_local` is denominated in (`"L"`, `"kg"`, `"kWh"`, `"month"`, `"each"`). |
| `coicop_code` | conditional | Required when `coicop_classification ∈ {source_curated, publisher_labeled}`. Absent when `deferred_gemini`. Typically 4-digit COICOP-2018 (e.g. `"01.1.1"`); coarser is acceptable when the source doesn't support finer. |
| `observation_hash` | yes | SHA-1 of the identifying tuple. Set LAST. |
| `subnational_area` | no | State / region / province for sources that break down sub-nationally. Null otherwise. |
| `city` | no | City name where applicable. |
| `district` | no | District / suburb (real-estate). |
| `bedrooms` | no | Real-estate listings — number of bedrooms. |
| `vehicle_type` | no | Real-estate / classifieds for vehicles. |
| `effective_from` | no | Tariff schedules — start of validity. |
| `source_url` | no | Permalink to the specific page / endpoint, when stable. |
| `notes` | no | Free-form per-row note (rare). |

### IndexObservation

Used for: CPI indexes (`analytical_role: cpi_benchmark`).

| Column | Required | Notes |
|---|---|---|
| `observation_date` | yes | ISO `YYYY-MM-DD`. The first day of the period the index labels (e.g. `"2026-05-01"` for May 2026 monthly CPI). |
| `period_kind` | yes | One of `monthly_avg`, `quarterly_avg`, `annual_avg`. CPIs are aggregated by definition. |
| `country` | yes | As above. |
| `source_key` | yes | Matches the YAML manifest. |
| `coicop_code` | yes | The COICOP code the index applies to (2-digit division `"01"`, or finer when the publisher exposes it). |
| `index_value` | yes | Numeric. |
| `index_base_period` | yes | Free-text label of the base period (`"2018=100"`, `"2010=100"`). |
| `observation_hash` | yes | SHA-1 of identifying tuple. Set LAST. |
| `subnational_area` | no | For NSOs that publish sub-national CPIs (rare). |
| `source_url` | no | Permalink. |
| `notes` | no | Free-form per-row note. |

Output files:
- PriceObservation rows → `data/prices/<region>/<subregion>/<country>/<source>/price_observations.csv`
- IndexObservation rows → `data/prices/<region>/<subregion>/<country>/<source>/index_observations.csv`
- Bucket 3 global series → `data/prices/_global/<source>/price_observations.csv`

The two files never mix.

---

## 3. Three location buckets

### Bucket 1 — Country-bound (the default)

Most price sources are country-bound: one country, one source, one fetcher.

```
src/prices/fetchers/
    eap/
        southeast_asia/
            indonesia/
                pertamina.py        # def fetch_id_pertamina(cutoff)
                bps_cpi.py          # def fetch_id_bps_cpi(cutoff)
            singapore/
                singstat_arp.py     # def fetch_sg_singstat_arp(cutoff)
                sp_group.py         # def fetch_sg_sp_group(cutoff)
        pacific_islands/
            fiji/
                fccc_fuel.py        # def fetch_fj_fccc_fuel(cutoff)
```

YAML manifest at `src/prices/configs/eap/southeast_asia/indonesia/pertamina.yaml`:

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: aggregate_proxy
coicop_classification: source_curated
coicop_codes: ["07.2.2", "04.5.4"]
source_key: id_pertamina
module: eap.southeast_asia.indonesia.pertamina
function: fetch_id_pertamina
url: https://mypertamina.id/fuels-harga
language: id
cadence: monthly
fallback_date: 2020-01-01
```

Expect this bucket to hold ~80% of fetchers across 38 EAP economies.

### Bucket 2 — Regional aggregator

One shared module covers many countries in a region with a single API/page shape. Each country gets a per-country wrapper file + a per-country YAML; rows are emitted per-country.

Examples: Shopee SEA (SG/MY/ID/PH/TH/VN), Watsons (HK/SG/MY/TW), Lazada SEA, possibly WB ICP if it covers many of our countries with one fetcher shape.

```
src/prices/fetchers/
    _shared/
        eap/
            shopee.py               # fetch_sg_shopee, fetch_my_shopee, ...
    eap/
        southeast_asia/
            singapore/
                shopee.py           # wrapper: re-exports fetch_sg_shopee
            malaysia/
                shopee.py           # wrapper: re-exports fetch_my_shopee
```

The shared module's design is an author choice — what matters is that each public name (`fetch_sg_shopee`, etc.) satisfies the contract. Two reasonable patterns:

**Pattern 2a — Simple per-country functions calling a shared helper:**

```python
"""Shopee SEA — shared module covering SG/MY/ID/PH/TH/VN."""

from datetime import date
import pandas as pd

_TLDS = {"sg": "sg", "my": "com.my", "id": "co.id", "ph": "ph", "th": "co.th", "vn": "vn"}
_CURRENCIES = {"sg": "SGD", "my": "MYR", "id": "IDR", "ph": "PHP", "th": "THB", "vn": "VND"}
_COUNTRIES = {"sg": "Singapore", "my": "Malaysia", "id": "Indonesia", "ph": "Philippines", "th": "Thailand", "vn": "Vietnam"}


def _fetch_one(cc: str, cutoff: date) -> pd.DataFrame | None:
    # ... HTTP + parse, returns rows for one country ...
    return pd.DataFrame(rows) if rows else None


def fetch_sg_shopee(cutoff: date) -> pd.DataFrame | None: return _fetch_one("sg", cutoff)
def fetch_my_shopee(cutoff: date) -> pd.DataFrame | None: return _fetch_one("my", cutoff)
def fetch_id_shopee(cutoff: date) -> pd.DataFrame | None: return _fetch_one("id", cutoff)
def fetch_ph_shopee(cutoff: date) -> pd.DataFrame | None: return _fetch_one("ph", cutoff)
def fetch_th_shopee(cutoff: date) -> pd.DataFrame | None: return _fetch_one("th", cutoff)
def fetch_vn_shopee(cutoff: date) -> pd.DataFrame | None: return _fetch_one("vn", cutoff)
```

Six explicit one-liners. Readable, debuggable, easy to grep for the per-country name.

**Pattern 2b — Closure factory.** Used in `src/fuel/fetchers/_shared/eca/autotraveler.py` when the supported-country set is large (~30 countries). For prices regional aggregators (likely 4–6 countries each), Pattern 2a is usually cleaner. Reach for 2b only when the per-country list is long enough that one-liners become noisy.

Per-country wrapper (`src/prices/fetchers/eap/southeast_asia/singapore/shopee.py`):

```python
"""Canonical wrapper for Shopee in Singapore."""

from prices.fetchers._shared.eap.shopee import fetch_sg_shopee

fetch_sg_shopee.__module__ = __name__
__all__ = ["fetch_sg_shopee"]
```

Per-country YAML (`src/prices/configs/eap/southeast_asia/singapore/shopee.yaml`):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: retailer_sku
coicop_classification: deferred_gemini   # SKU names go through Gemini
source_key: sg_shopee
module: eap.southeast_asia.singapore.shopee
function: fetch_sg_shopee
url: https://shopee.sg
language: en
cadence: daily
fallback_date: 2024-01-01
```

### Bucket 3 — Truly global aggregate series (rare)

Single source emits rows tagged with aggregate-region labels (`country="Global"`, `country="EAP"`). One YAML, no per-country files. Expect 2–3 sources total across the entire skill (Brent/WTI from Investing.com, World Bank Pink Sheet, IMF FX possibly).

```
src/prices/fetchers/
    _global/
        wb_pink_sheet.py
```

YAML at `src/prices/configs/_global/wb_pink_sheet.yaml`:

```yaml
scaffolding: fetcher
extraction_pattern: tabular_download
analytical_role: aggregate_proxy
coicop_classification: source_curated
coicop_codes: ["01", "04", "07"]
source_key: wb_pink_sheet
module: _global.wb_pink_sheet
function: fetch_wb_pink_sheet
url: https://www.worldbank.org/en/research/commodity-markets
language: en
cadence: monthly
fallback_date: 1960-01-01
notes: Emits rows with country="Global".
```

**Do not confuse Bucket 2 with Bucket 3.** A source like WB ICP that emits one row per country per ICP basket item is Bucket 2 (per-country YAMLs, shared module). Bucket 3 is reserved for sources whose semantics are inherently supra-national (a global commodity benchmark price has no country).

---

## 4. Helpers (optional toolbox)

`src/prices/fetchers/utils.py` — these are available when convenient. Nothing in the contract requires them; nothing prevents a fetcher from declining to use any of them.

```python
"""Shared helpers for prices fetchers — use when convenient, not mandatory."""

import hashlib
from datetime import datetime, timezone

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

_HASH_SEP = b"\x00"


def get_scrape_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_hash(row: dict, identifying_fields: list[str]) -> str:
    """SHA-1 over a fixed identifying tuple, NULL-separated to avoid collisions."""
    parts = [str(row.get(f, "")) for f in identifying_fields]
    return hashlib.sha1(_HASH_SEP.join(p.encode("utf-8") for p in parts)).hexdigest()


def get_session(retries: int = 3, backoff: float = 0.5) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=retries, backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "pacific-observatory/prices (+research)"})
    return s


def safe_last_date(df: pd.DataFrame, col: str = "observation_date"):
    """Return the latest observation_date in df, or None."""
    if df is None or df.empty:
        return None
    return pd.to_datetime(df[col]).max().date()
```

`make_template()` from the previous draft is removed — it baked the unified row schema into a helper that's now wrong (two schemas, no single canonical column set). Construct row dicts directly; the schema tables in §2 are the reference.

---

## 5. Worked examples

Read what's relevant to your case. Patterns to copy: HTTP plumbing, parsing tactics, COICOP map shape, OCR fallback, currency-magnitude sanity checks. Patterns to NOT mechanically copy: module-level constant naming, file shape — those vary per source.

### 5.1 REST API — Pertamina (Indonesia, fuel)

`analytical_role: aggregate_proxy`, `coicop_classification: source_curated`, emits PriceObservation.

```python
"""Pertamina retail fuel prices — public JSON endpoint."""

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE_URL = "https://mypertamina.id/api/fuel-prices"
_COUNTRY = "Indonesia"
_CURRENCY = "IDR"
_SOURCE_KEY = "id_pertamina"

# Petrol/diesel → transport fuels (07.2.2); kerosene → housing fuels (04.5.4).
_COICOP_MAP = {
    "Pertalite": "07.2.2",
    "Pertamax": "07.2.2",
    "Pertamax Turbo": "07.2.2",
    "Dexlite": "07.2.2",
    "Pertamina Dex": "07.2.2",
    "Solar": "07.2.2",
    "Minyak Tanah": "04.5.4",
}

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]


def fetch_id_pertamina(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_BASE_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    rows = []
    for region in payload.get("data", []):
        wilayah = region["region_name"]
        for entry in region["products"]:
            obs_date = entry["effective_date"]
            if date.fromisoformat(obs_date) <= cutoff:
                continue
            item = entry["product_name"]
            coicop = _COICOP_MAP.get(item)
            if not coicop:
                logger.warning("No COICOP mapping for Pertamina product %r — dropping row", item)
                continue
            row = {
                "observation_date": obs_date,
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "subnational_area": wilayah,
                "item_name": item,
                "price_local": float(entry["price"]),
                "currency": _CURRENCY,
                "unit": "L",
                "coicop_code": coicop,
                "source_url": _BASE_URL,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
```

### 5.2 PDF with OCR fallback — FCCC (Fiji, monthly fuel orders)

```python
"""FCCC Fiji monthly fuel price orders — PDF with OCR fallback."""

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://fccc.gov.fj/orders/"
_COUNTRY = "Fiji"
_CURRENCY = "FJD"
_SOURCE_KEY = "fj_fccc_fuel"

_COICOP_MAP = {
    "Motor Spirit Premium": "07.2.2",
    "Motor Spirit": "07.2.2",
    "Premix": "07.2.2",
    "Diesel": "07.2.2",
    "Kerosene": "04.5.4",
}

_IDENT = ["source_key", "observation_date", "item_name"]


def _ocr_pdf(pdf_bytes: bytes) -> str:
    """OCR fallback for image-only PDFs."""
    import pytesseract
    from pdf2image import convert_from_bytes
    logger.info("Falling back to OCR for %s", _SOURCE_KEY)
    pages = convert_from_bytes(pdf_bytes, dpi=300)
    return "\n".join(pytesseract.image_to_string(p) for p in pages)


def _parse_schedule_1(text: str, order_date: date) -> list[dict]:
    """Anchor on the LAST 'SCHEDULE 1' occurrence; stop at 'Drum Sale' / 'Bulk'.

    Re-published orders with corrigenda often leave the original (stale) Schedule 1
    earlier in the document. The last occurrence is the authoritative one.
    """
    last = text.rfind("SCHEDULE 1")
    if last < 0:
        return []
    end = min((i for i in (text.find("Drum Sale", last), text.find("Bulk", last)) if i > 0),
              default=len(text))
    retail = text[last:end]

    rows = []
    for line in retail.splitlines():
        m = re.match(r"(?P<item>[A-Za-z][\w\- ]+?)\s+(?P<price>\d+\.\d{2,4})", line.strip())
        if not m:
            continue
        item = m["item"].strip()
        coicop = _COICOP_MAP.get(item)
        if not coicop:
            logger.warning("No COICOP mapping for FCCC item %r — dropping row", item)
            continue
        row = {
            "observation_date": order_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item,
            "price_local": float(m["price"]),
            "currency": _CURRENCY,
            "unit": "L",
            "coicop_code": coicop,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_fj_fccc_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    # ... discover and download each monthly PDF after cutoff (omitted) ...
    pdf_bytes = b""
    order_date = date.today()  # parsed from PDF filename in real impl

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    if not text.strip():
        text = _ocr_pdf(pdf_bytes)

    rows = _parse_schedule_1(text, order_date)
    return pd.DataFrame(rows) if rows else None
```

### 5.3 Tabular download (XLS) — SingStat ARP (Singapore, average retail prices)

`analytical_role: official_avg`. `coicop_classification: source_curated` if items are stable (recommended for SingStat ARP — fewer than 50 stable items); `deferred_gemini` if the table churns.

```python
"""SingStat Average Retail Prices of Selected Consumer Items — XLS download."""

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_XLS_URL = "https://www.singstat.gov.sg/-/media/files/.../arp.xlsx"
_COUNTRY = "Singapore"
_CURRENCY = "SGD"
_SOURCE_KEY = "sg_singstat_arp"

_COICOP_MAP = {
    "Rice, white, premium 1kg": "01.1.1",
    "Bread, sliced loaf 600g": "01.1.1",
    "Eggs, fresh, large 10s": "01.1.4",
    # ... real impl: ~30–50 entries ...
}

_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_sg_singstat_arp(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_XLS_URL, timeout=60)
    resp.raise_for_status()
    xls = pd.read_excel(io.BytesIO(resp.content), sheet_name=0, header=[0, 1])

    long = xls.melt(id_vars=[xls.columns[0]], var_name="period", value_name="price_local")
    long.columns = ["item_name", "period", "price_local"]
    long["observation_date"] = pd.to_datetime(long["period"], format="%Y %b").dt.strftime("%Y-%m-%d")
    long = long[pd.to_datetime(long["observation_date"]) > pd.Timestamp(cutoff)]

    rows = []
    for _, r in long.iterrows():
        item = str(r["item_name"]).strip()
        coicop = _COICOP_MAP.get(item)
        if not coicop:
            logger.warning("No COICOP mapping for SingStat item %r — dropping row", item)
            continue
        row = {
            "observation_date": r["observation_date"],
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item,
            "price_local": float(r["price_local"]),
            "currency": _CURRENCY,
            "unit": "each",  # real impl: parse unit from item description
            "coicop_code": coicop,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
```

### 5.4 HTML scrape — SP Group (Singapore, regulated electricity tariff)

`analytical_role: tariff`. The entire source is COICOP 04.5.1 — a single-value `_COICOP_MAP` (or a constant).

```python
"""SP Group Singapore — regulated electricity tariff (HTML)."""

import logging
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_TARIFF_URL = "https://www.spgroup.com.sg/.../regulated-tariff"
_COUNTRY = "Singapore"
_CURRENCY = "SGD"
_SOURCE_KEY = "sg_sp_group"
_COICOP = "04.5.1"  # Electricity, all plans

_IDENT = ["source_key", "effective_from", "item_name"]


def fetch_sg_sp_group(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_TARIFF_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    effective_from = soup.select_one(".tariff-effective-from").get_text(strip=True)
    if date.fromisoformat(effective_from) <= cutoff:
        return None

    rows = []
    for band in soup.select(".tariff-band"):
        row = {
            "observation_date": effective_from,
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": band.select_one(".band-name").get_text(strip=True),
            "price_local": float(band.select_one(".band-rate").get_text(strip=True)),
            "currency": _CURRENCY,
            "unit": "kWh",
            "coicop_code": _COICOP,
            "effective_from": effective_from,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
```

### 5.5 CPI (IndexObservation) — BPS Indonesia

`analytical_role: cpi_benchmark`, `coicop_classification: publisher_labeled` (with a language map). Emits IndexObservation, NOT PriceObservation.

```python
"""BPS Indonesia CPI — COICOP 2018 13-division grouping, monthly."""

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_URL = "https://webapi.bps.go.id/v1/api/list"  # placeholder
_COUNTRY = "Indonesia"
_SOURCE_KEY = "id_bps_cpi"
_BASE_PERIOD = "2018=100"

# Publisher labels are in Bahasa; map to COICOP 2-digit divisions.
_COICOP_MAP = {
    "Makanan, Minuman dan Tembakau": "01",
    "Pakaian dan Alas Kaki": "03",
    "Perumahan, Air, Listrik, dan Bahan Bakar Rumah Tangga": "04",
    "Perlengkapan, Peralatan dan Pemeliharaan Rutin Rumah Tangga": "05",
    "Kesehatan": "06",
    "Transportasi": "07",
    "Informasi, Komunikasi, dan Jasa Keuangan": "08",
    "Rekreasi, Olahraga, dan Budaya": "09",
    "Pendidikan": "10",
    "Penyediaan Makanan dan Minuman/Restoran": "11",
    "Perawatan Pribadi dan Jasa Lainnya": "12",
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def fetch_id_bps_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_API_URL, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    rows = []
    for entry in payload.get("data", []):
        obs_date = entry["period"]  # "YYYY-MM-01"
        if date.fromisoformat(obs_date) <= cutoff:
            continue
        for label, idx in entry["divisions"].items():
            coicop = _COICOP_MAP.get(label)
            if not coicop:
                logger.warning("No COICOP mapping for BPS label %r — dropping row", label)
                continue
            row = {
                "observation_date": obs_date,
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": float(idx),
                "index_base_period": _BASE_PERIOD,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
```

### 5.6 CPI with non-COICOP-2018 grouping — SingStat (Singapore)

Same shape as 5.5 (publisher_labeled, IndexObservation), but the publisher's division taxonomy doesn't map 1:1 to COICOP 2018. SingStat publishes 11 divisions, missing COICOP 02 (alcohol & tobacco — folded into "Miscellaneous Goods & Services") and merging COICOP 11/12/13 differently. The translation map handles this; missing divisions stay missing (they don't get a sentinel).

```python
"""SingStat M213751 — Consumer Price Index, 2024 base, monthly."""

_DIVISION_MAP = {
    "1.01": "01",   # Food Excl Serving        → COICOP 01
    "1.02": "03",   # Clothing & Footwear      → COICOP 03
    "1.03": "04",   # Housing & Utilities      → COICOP 04
    "1.04": "05",   # Household Durables/Svcs  → COICOP 05
    "1.05": "06",   # Health                   → COICOP 06
    "1.06": "07",   # Transport                → COICOP 07
    "1.07": "08",   # Information & Comms      → COICOP 08
    "1.08": "09",   # Recreation/Sport/Culture → COICOP 09
    "1.09": "10",   # Education                → COICOP 10
    "1.10": "12",   # Misc Goods & Services    → COICOP 12 (folds 12 + parts of 13)
    "1.11": "11",   # Food & Bev Serving Svcs  → COICOP 11
}
# COICOP 02 (alcohol & tobacco) intentionally absent — SingStat folds into Misc.

# The All-Items headline (series "1") is NOT emitted: IndexObservation requires
# coicop_code, and there is no sanctioned sentinel for headline CPI yet.
# Open design question — see "Headline CPI" note in SKILL.md.
```

Two SingStat-specific API quirks repeat across SG fetchers (and likely DGBAS Taiwan, DOSM Malaysia, BPS Indonesia, others using TableBuilder-style endpoints):

1. **The `/tabledata` endpoint silently caps at ~3 series unless `seriesNoORrowNo=<id>` is passed per-series.** `limit=2000` does *not* unlock the rest; the cap is fixed and undocumented. Always fetch the series list from `/metadata` first, then loop per-series. See `references/probe_patterns.md` § "Stats-office REST APIs".
2. **`between=YYYY-MM,YYYY-MM` plus comma-separated `seriesNoORrowNo` returns zero rows.** The two filters don't compose. Pick one and filter the other client-side — usually easier to fetch the full time series per series and slice on the cutoff.

---

## 6. Key invariants

These are the failure modes worth memorizing — every one has bit us in prior runs.

- **`observation_hash` is set LAST.** Hashing before populating every identifying field produces duplicate rows on re-run. The hash is computed by `make_hash(row, _IDENT)` after every other field in `_IDENT` is set.
- **Bounds-check prices.** If `price_local` is outside a plausible range for the unit, log a warning and drop the row. The most common cause of 100× errors is currency-display shorthand (IDR `"12,90"` meaning `12,900`, not `12.90`).
- **`currency` comes from `countries.yaml`, not the price symbol.** "$" on a Brunei site is BND, not USD. Set the currency at module load, never parse it.
- **PDF Schedule 1 anchoring: use the LAST occurrence.** Re-published regulator orders leave stale Schedule 1 tables earlier in the document. `text.rfind("SCHEDULE 1")` is correct; `text.find` is wrong.
- **OCR fallback runs only when `pdfplumber.extract_text()` returns empty.** Always log when OCR ran — it's ~5–10× slower and worth surfacing.
- **Playwright import is guarded.** Wrap `from playwright.sync_api import sync_playwright` in a `try` so the module stays importable on machines without Playwright.
- **Drop unmappable COICOP rows; don't emit `null`.** When `coicop_classification` is `source_curated` or `publisher_labeled` and the map misses, log a warning and drop. A row with null `coicop_code` that should have been populated is pollution masquerading as coverage.
- **One fetcher = one schema.** A fetcher emits either PriceObservation rows or IndexObservation rows, never both. If a source publishes both, write two fetchers and two YAMLs.
- **Idempotence is the caller's contract.** Drop rows where `observation_date <= cutoff`. The collect layer handles cursor management; the fetcher does not.
- **`_IDENT` is module-private.** Different schemas and observation cadences need different identifying tuples. Per-SKU-per-day (`source_key`, `observation_date`, `item_name`, `subnational_area`) differs from per-COICOP-per-month (`source_key`, `observation_date`, `coicop_code`).
