# src/fuel/fetchers/

Per-country modules that collect fuel price observations from
government and industry sources.

## Structure

```
fetchers/
├── _common/              Shared utilities (PDF parsing, date helpers)
├── _examples/
│   └── fetcher_template.py   Annotated template — start here
├── pacific/              Pacific region fetchers
│   ├── australia.py      AU FuelWatch, FuelCheck, ACCC, AIP
│   ├── fiji.py           Fiji FCCC PDF parser
│   ├── new_zealand.py    NZ MBIE weekly data
│   └── ...
└── README.md
```

## Fetcher Contract

Every fetcher is a function:

```python
def fetch_xx(cutoff: date) -> pd.DataFrame | None
```

- `cutoff`: last known observation date — only return data after this
- Returns DataFrame with columns: `observation_date`, `country`,
  `fuel_product`, `price_local`, `currency`, `source_key`
  (+ optional: `unit`, `subnational_area`, `city`, `address`)
- Returns `None` or empty DataFrame if no new data
- Must not modify stored data — collect layer handles append/dedup

## Common Patterns

| Pattern | Example | Utility |
|---------|---------|---------|
| HTML table | `pacific/new_zealand.py` | BeautifulSoup |
| JSON API | `pacific/timor_leste.py` | requests |
| PDF table | `pacific/fiji.py` | `_common/pdf.py` + pdfplumber |
| Excel download | `pacific/japan.py` | openpyxl |
| Multi-page scrape | `pacific/thailand.py` | session + pagination |

## Adding a New Fetcher

See [docs/fuel/HOW_TO_ADD_NEW_FETCHER.md](../../../docs/fuel/HOW_TO_ADD_NEW_FETCHER.md)
