# src/text/analysis/

EPU (Economic Policy Uncertainty) index calculation, sentiment
analysis, and topic indices from scraped newspaper articles.

## Key Modules

| Module | Purpose |
|--------|---------|
| `main.py` | Pipeline orchestrator — loads articles, runs analysis |
| `epu.py` | EPU index: ratio → standardize → aggregate → normalize |
| `indices.py` | Extended indices: breadth, intensity, pairwise |
| `modeling.py` | LASSO regression for inflation prediction |
| `sentiment.py` | Sentiment scoring |
| `data.py` | CSV file reading utilities |
| `utils.py` | Text preprocessing, keyword pattern building |

## Keywords

`keywords/` contains 26 language directories, each with:
- `epu.json` — Economic, Policy, Uncertainty terms
- `actors.json` — Government actors, institutions
- `topics.json` — Topic-specific terms (inflation, trade, etc.)

Keywords are per-language, shared across all regions. English
keywords apply to Ukraine newspapers the same as Fiji ones.

Languages: bislama, chinese_simplified, chinese_traditional, en,
fijian, filipino, fr, hindi, indo, japanese, km, korean, lao,
malay, maori, marshallese, mn, palauan, samoan,
solomon_islands_pijin, tamil, tetum, thai, tok_pisin, tongan,
vietnamese

## EPU Methodology

1. Count keyword matches per article (E, P, U categories)
2. Calculate ratio: EPU articles / total articles per newspaper
3. Standardize by newspaper (divide by std dev)
4. Aggregate across newspapers (mean or weighted)
5. Normalize to 100 over reference period
