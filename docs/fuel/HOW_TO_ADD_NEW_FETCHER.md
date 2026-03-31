# How to Add a New Fuel Price Fetcher

This guide walks through adding a new fuel price data source. A
"fetcher" is a Python function that pulls price data from a website,
API, PDF, or Excel file and returns it as a DataFrame.

## Prerequisites

- Python 3.11+
- The repository cloned and installed: `pip install -e .`
- The country must exist in `src/configs/countries.yaml`

## Quick Start (5 minutes for simple API/table sources)

1. Create config: `src/fuel/configs/{region}/{country}.yaml`
2. Create fetcher: `src/fuel/fetchers/{region}/{country}.py`
3. Test: `po fuel collect --source {source_key} --dry-run`
4. Run: `po fuel collect --source {source_key}`

## Step 1: Add the Country (if new)

If the country doesn't exist in `src/configs/countries.yaml`, add it:

```yaml
germany:
  name: Germany
  iso3: DEU
  region: europe
  currency: EUR
```

And add the slug to the region in `src/configs/regions.yaml`.

## Step 2: Create the YAML Config

Copy the template:
```bash
cp src/fuel/configs/_examples/country_template.yaml \
   src/fuel/configs/{region}/{country}.yaml
```

Fill in the config. Key sections:

### Products

Define what fuel types this country tracks:

```yaml
products:
  diesel_standard:
    family: diesel           # gasoline | diesel | lpg | kerosene | cng | electricity_ev
    grade: standard          # Qualifier: regular, premium, midgrade, branded, etc.
    series_key: diesel_standard
```

### Sources

Define where data comes from:

```yaml
sources:
  de_bafa_monthly:
    module: europe.germany          # Path under src/fuel/fetchers/
    function: fetch_bafa            # Function name in that module
    url: https://www.bafa.de/...    # Source homepage
    description: "Monthly petroleum product prices from BAFA"
    products:
      "Dieselkraftstoff": diesel_standard
      "Superbenzin":      gasoline_regular
```

The `products` mapping translates raw product names (as they appear in
the source) to the product keys defined above.

## Step 3: Write the Fetcher

Copy the template:
```bash
cp src/fuel/fetchers/_examples/fetcher_template.py \
   src/fuel/fetchers/{region}/{country}.py
```

### The Fetcher Contract

```python
def fetch_source_name(cutoff: date) -> pd.DataFrame | None:
```

- **Input**: `cutoff` — the date of the last observation we have.
  Only return data with `observation_date > cutoff`.
- **Output**: DataFrame with these columns:

| Column | Required | Type | Description |
|--------|----------|------|-------------|
| `observation_date` | Yes | str (YYYY-MM-DD) | When the price was observed |
| `country` | Yes | str | Country name (match countries.yaml) |
| `fuel_product` | Yes | str | Raw product name (mapped via YAML config) |
| `price_local` | Yes | float | Price in local currency |
| `currency` | Yes | str | ISO 4217 code |
| `source_key` | Yes | str | Must match YAML source key |
| `unit` | No | str | Default: "L" (liter) |
| `subnational_area` | No | str | State/province |
| `city` | No | str | City name |
| `address` | No | str | Station address |

- Return `None` or empty DataFrame if no new data.
- The fetcher must **not** modify stored data — the collect layer
  handles dedup and storage.

### Common Extraction Patterns

**HTML table** (see `pacific/new_zealand.py`):
```python
from core.http import make_session
from bs4 import BeautifulSoup

def fetch_mbie(cutoff):
    session = make_session()
    resp = session.get("https://...")
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.select_one("table.fuel-prices")
    # ... parse rows into list of dicts
```

**JSON API** (see `pacific/timor_leste.py`):
```python
def fetch_anp_api(cutoff):
    session = make_session()
    resp = session.get("https://api.example.com/prices")
    data = resp.json()
    # ... extract from JSON structure
```

**PDF table** (see `pacific/fiji.py`):
```python
import pdfplumber
from io import BytesIO

def fetch_fccc(cutoff):
    session = make_session()
    resp = session.get("https://fccc.gov.fj/latest.pdf")
    pdf = pdfplumber.open(BytesIO(resp.content))
    table = pdf.pages[0].extract_table()
    # ... parse table rows
```

**Excel download** (see `pacific/japan.py`):
```python
def fetch_anre(cutoff):
    session = make_session()
    resp = session.get("https://example.go.jp/prices.xlsx")
    df = pd.read_excel(BytesIO(resp.content), sheet_name="Sheet1")
    # ... filter and transform
```

### Tips

- Use `core.http.make_session()` for HTTP requests (sets browser-like
  headers to avoid blocks).
- Always check `response.raise_for_status()` after requests.
- Handle date parsing carefully — different sources use different
  formats. See `fetchers/_common/dates.py` for helpers.
- For PDF sources, see `fetchers/_common/pdf.py` for shared utilities.
- Log progress: `import logging; logger = logging.getLogger(__name__)`

## Step 4: Test

```bash
# Preview what would happen (no data written)
po fuel collect --source de_bafa_monthly --dry-run

# Run the fetcher for real
po fuel collect --source de_bafa_monthly

# Verify the output
cat data/fuel/germany/de_bafa_monthly/observations.csv | head

# Build enriched dataset
po fuel build --country germany

# Check source health
po status
```

## Step 5: Commit

Commit both files together:
- `src/fuel/configs/{region}/{country}.yaml`
- `src/fuel/fetchers/{region}/{country}.py`

Update `src/fuel/fetchers/README.md` if the fetcher uses a novel
pattern not listed there.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 403 Forbidden | Source may block scripts. Check if auth/cookies needed. |
| Empty DataFrame | Verify cutoff logic — are you filtering too aggressively? |
| Date parse errors | Check source date format. Use `_common/dates.py` helpers. |
| Encoding issues | Pass `encoding="utf-8"` (or source-specific encoding). |
| SSL errors | Try `session.verify = False` as last resort (not recommended). |
| PDF table misparse | Use `pdfplumber.extract_table(table_settings=...)` to tune. |

## Reference

- Config template: `src/fuel/configs/_examples/country_template.yaml`
- Fetcher template: `src/fuel/fetchers/_examples/fetcher_template.py`
- Config schema: [docs/fuel/YAML_CONFIG_REFERENCE.md](YAML_CONFIG_REFERENCE.md)
- Pipeline docs: [docs/fuel/PIPELINE.md](PIPELINE.md)
