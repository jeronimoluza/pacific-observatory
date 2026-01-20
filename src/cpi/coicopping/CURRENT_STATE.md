# Technical Overview: COICOP Product Parsing System

## 1. Overall Pipeline / Architecture

The system processes supermarket product data through a **4-step pipeline** orchestrated by `main.py`:

### Data Flow

```
[Scrapy JSONL + Wayback JSON]
    ↓ loading.py
[Raw DataFrame with price, product_name, category, url_hash, country, source]
    ↓ cleaning.py + prestep.py
[Cleaned DataFrame with product_only, product_w_cat]
    ↓ extract_quantities.py
[DataFrame with amount, units, unit_value]
    ↓ coicop_matching.py (Gemini AI)
[Final DataFrame with coicop_code, coicop_title]
    ↓
[all_countries_supermarket_prices.csv]
```

### Main Steps

1. **Data Loading** (`loading.py`)
   - Loads scrapy JSONL files from `data/cpi/price_scraping/{country}/{source}/raw_items/`
   - Loads wayback JSON files from `wayback_machine_data/items/`
   - Applies currency mapping from scrapy to wayback data
   - Applies product_name/category mapping from latest scrapy items to wayback items (by `url_hash`)
   - Extracts date from `scraped_at` or `wayback_timestamp`
   - Drops rows with null prices

2. **Cleaning & Preparation** (`cleaning.py`, `prestep.py`)
   - Source-specific string removal via `string_cleaning.json`
   - Special handling for `samoa_market` (removes combos, vouchers, availability brackets)
   - Creates `product_only` by removing quantities from `product_name`
   - Creates `product_w_cat` by combining `product_only` with cleaned category

3. **Quantity Extraction** (`extract_quantities.py`)
   - Extracts `amount` (weight/volume) and `units` (count) from product names
   - Calculates `unit_value` (price per kg/lt/mt or price per unit)

4. **COICOP Classification** (`coicop_matching.py`)
   - Downloads COICOP 2018 categories from UN Stats
   - Sends products to Gemini AI in batches of 600
   - Incrementally saves classifications to `gemini_classification.csv`
   - Merges classifications back to quantity data

---

## 2. Quantity and Unit Extraction

### Representation

Quantities are represented as **two separate string fields**:

| Field | Description | Example Values |
|-------|-------------|----------------|
| `amount` | Weight/volume with unit | `"132 g"`, `"1 kg"`, `"500 ml"`, `None` |
| `units` | Count (numeric string) | `"1"`, `"6"`, `"24"`, `"168"` |

### Extraction Logic (`extract_amount_and_units()`)

The function applies regex patterns in **priority order**:

1. **`PER_KG_REGEX`** → `amount = "1 kg"`, `units = None`
2. **`PER_EACH_REGEX`** → `amount = None`, `units = "1"`
3. **`X_SEPARATOR_REGEX`** → Handles patterns like `"30 x 105g"`, `"250mls x 24"`
4. **`AMOUNT_REGEX`** → Standard weight/volume patterns
5. **`UNITS_REGEX`** → Standard count patterns
6. **Default** → `units = "1"` if nothing found

### Regex Patterns (from `regex_config.py`)

| Pattern | Purpose | Examples Matched |
|---------|---------|------------------|
| `AMOUNT_REGEX` | Weight/volume | `"9kg"`, `"9-15kg"`, `"500ml"` |
| `UNITS_REGEX` | Count units | `"6 pack"`, `"6-10 pack"`, `"6 per/ pack"` |
| `X_SEPARATOR_REGEX` | Multiplied quantities | `"30 x 105g"`, `"x 500"`, `"28 x 6pack"` |
| `PER_KG_REGEX` | Per-kilogram pricing | `"per/kg"`, `"per kg"`, `"(per kg)"` |
| `PER_EACH_REGEX` | Per-unit pricing | `"per/each"`, `"per ea"`, `"(each)"` |

### Unit Lists (centralized in `regex_config.py`)

- **`COUNT_UNITS`**: `can, cans, ct, pack, packs, piece, pieces, pk, pc, pcs, box, boxes, jar, jars, bag, bags`
- **`AMOUNT_UNITS`**: `g, gm, kg, lb, lbs, oz, ml, mls, l, litre, ltrs, ltr, gallon, gal, m, cm, ft, feet, in, inch, inches`

---

## 3. Multiple Quantities, Packs, and Promotions

### Multiple Quantities (X-Separator Handling)

The `X_SEPARATOR_REGEX` handles bidirectional patterns:

| Input | Interpretation | Result |
|-------|----------------|--------|
| `"30 x 105g"` | 30 items of 105g each | `amount="105 g"`, `units="30"` |
| `"250mls x 24"` | 24 items of 250ml each | `amount="250 mls"`, `units="24"` |
| `"28 x 6pack"` | 28 × 6 = 168 total | `amount=None`, `units="168"` |
| `"x 500"` | 500 units | `amount=None`, `units="500"` |

**Logic**: Checks left side first for amount units, then right side. If a count unit is found (e.g., `6pack`), it **multiplies** the numbers.

### Range Handling

For ranges like `"9-15kg"` or `"6-10 pack"`:
- Uses the **average rounded down**: `int((9 + 15) / 2) = 12`

### Promotions

**Not explicitly handled.** The system does not detect or flag promotional pricing, bundles, or special offers. Promotional text would be treated as regular product name content.

---

## 4. Unit Conversion and Standardization

### Conversion Tables (`unit_conversions.py`)

All units are converted to **three standard units**:

| Category | Standard Unit | Conversions |
|----------|---------------|-------------|
| Weight | `kg` | `g=0.001`, `oz=0.0283495`, `lb=0.453592` |
| Volume | `lt` | `ml=0.001`, `gallon=3.78541` |
| Length | `mt` | `cm=0.01`, `ft=0.3048`, `in=0.0254` |

### Unit Value Calculation (`calculate_unit_value()`)

```
unit_value = price / (converted_amount × count)
```

**Logic**:

1. Parse price string to float (handles `"$18.91 NZD Incl. VAGST"`)
2. Parse units count (default: 1)
3. If no amount: `unit_value = price / count`
4. If amount has unknown unit: `unit_value = price / count`
5. If amount has known unit: convert to standard, then `price / (converted × count)`

### Price Parsing

The `parse_price()` function extracts the first numeric value from strings like:
- `"$18.91 NZD Incl. VAGST"` → `18.91`
- `"15.00 K"` → `15.00`

---

## 5. Product Acceptance, Rejection, and Flagging

### Acceptance Criteria

- **Implicit acceptance**: All products with non-null prices are processed
- **No explicit validation** of extracted quantities
- **No confidence scoring** on extraction results

### Rejection Criteria

| Stage | Rejection Rule |
|-------|----------------|
| Loading | Rows with `price = NaN` are dropped |
| Cleaning (samoa_market only) | Products matching `"birthday combo #"`, `"aiga combo "`, or `'voucher "redeem at ah liki wholesale"'` are removed |

### Flagging / Ambiguity

**No explicit ambiguity flagging exists.** Products that fail to match any regex pattern simply get:
- `amount = None`
- `units = "1"` (default)
- `unit_value = price / 1` (price per unit)

**Unclear cases**:
- If multiple regex patterns match, only the **first match** is used
- No logging or flagging of products where extraction may be unreliable

---

## 6. Heuristics, Rules, and Confidence Scoring

### Heuristics Used

| Heuristic | Location | Description |
|-----------|----------|-------------|
| **First match wins** | `extract_amount_and_units()` | Uses first regex match for amount/units |
| **Range averaging** | `extract_amount_and_units()` | `"9-15kg"` → `12 kg` |
| **Pack multiplication** | X-separator logic | `"28 x 6pack"` → `168` units |
| **Default unit = 1** | `extract_amount_and_units()` | If no count found, assume 1 |
| **Latest scrapy value** | `loading.py` | Wayback data inherits product_name/category from latest scrapy item |
| **Most common currency** | `loading.py` | Wayback data inherits currency from most common scrapy value per source |

### Text Cleaning Heuristics

| Heuristic | Location | Description |
|-----------|----------|-------------|
| **Remove parenthetical content** | `clean_product_only()` | `"product (info)"` → `"product"` |
| **Remove bracketed content** | `clean_product_only()` | `"product [info]"` → `"product"` |
| **Remove accents** | `clean_product_only()` | `"café"` → `"cafe"` |
| **Remove stopwords** | `clean_product_w_cat()` | NLTK stopwords + size words + count units |
| **Remove words with numbers** | `clean_product_w_cat()` | `"8x24s"` removed |
| **Remove single characters** | `clean_product_w_cat()` | `"x"`, `"o"` removed |

### Confidence Scoring

**None implemented.** The system does not produce confidence scores for:
- Quantity extraction accuracy
- COICOP classification confidence
- Unit value reliability

---

## 7. Assumptions and Limitations

### Assumptions

1. **Product names contain quantity information** in recognizable patterns
2. **First regex match is correct** (no disambiguation)
3. **Prices are in local currency** per source (no multi-currency handling within a source)
4. **Wayback data shares product metadata** with latest scrapy data for same `url_hash`
5. **COICOP classification is deterministic** per `product_w_cat` string

### Limitations

1. **No promotion detection** — promotional bundles may produce incorrect unit values
2. **No ambiguity handling** — conflicting patterns are not flagged
3. **No confidence scoring** — all extractions treated equally
4. **Limited unit vocabulary** — units not in `AMOUNT_UNITS`/`COUNT_UNITS` are ignored
5. **Single amount per product** — products with multiple distinct amounts (e.g., "100g + 50g bonus") only capture first
6. **No validation of extracted values** — implausible values (e.g., 0.001 kg for a car) are not flagged
7. **Gemini API dependency** — COICOP classification requires external API and may fail/timeout
8. **No retry logic for failed extractions** — products that fail regex matching are silently defaulted

### Unclear Behavior

- **What happens if `product_name` is empty?** — Returns `(None, "1")`
- **What if price is negative?** — Returns `None` for `unit_value`
- **What if amount value is 0?** — Returns `price / count` (ignores amount)

---

## 8. File Summary

| File | Purpose |
|------|---------|
| `main.py` | Pipeline orchestration |
| `loading.py` | Load scrapy + wayback data |
| `cleaning.py` | Source-specific string cleaning |
| `prestep.py` | Create `product_only` and `product_w_cat` |
| `regex_config.py` | Centralized regex patterns and unit lists |
| `extract_quantities.py` | Extract amount, units, calculate unit_value |
| `unit_conversions.py` | Conversion factors to kg/lt/mt |
| `coicop_matching.py` | Gemini AI classification workflow |
| `coicop_categories.py` | Download and process COICOP Excel |
| `string_cleaning.json` | Source-specific strings to remove |
