---
name: translate-english-keywords
description: "Generate per-language EPU/actors/topics keyword JSON files for the text pipeline by translating from `src/text/analysis/keywords/en/` into a target language with Claude (no googletrans). Use whenever the user wants to add or backfill a language for `po text build`, mentions a missing language folder under `src/text/analysis/keywords/`, says EPU is producing zero matches for some country, asks to translate epu.json / actors.json / topics.json, or onboards a region whose source YAMLs use a `language:` tag that doesn't yet have a keyword folder. Also use even when the user phrases it casually (\"set up Swahili\", \"we need Portuguese keywords\", \"translate the keywords for Tanzania\"). Always produce the array-of-variants format mirroring `keywords/arabic/epu.json` — never the per-term dict format from the legacy googletrans tool."
---

# Translate English Keywords (EPU / Actors / Topics)

Generate Pacific Observatory text-pipeline keyword files for a new language by
translating directly from the English source-of-truth at
`src/text/analysis/keywords/en/`. The translations go to
`src/text/analysis/keywords/<lang>/{epu,actors,topics}.json`.

The point of this skill is to produce keyword sets that **actually match real
news article text**, not just dictionary translations. That requires
morphological coverage, domain-correct word sense, and English fallbacks for
code-mixed prose — none of which a per-term machine translator gives you.

## Why Claude direct, not googletrans

The codebase ships a googletrans-based translator
(`src/text/analysis/translate_keywords.py`) and you should NOT use it for this
skill. Concrete reasons, learned from the existing per-language files:

- **Per-term dict format throws away matches.** `translate_keywords.py` emits
  `{"english_term": "translated_term"}` — exactly one form per English term. A
  matcher searching real article copy needs the singular *and* plural,
  definite *and* indefinite, masculine *and* feminine, plus common synonyms.
- **Domain word sense.** `fr/actors.json` has `"cabinet": "armoire"` (a
  closet), `"rate decision": "décision tarifaire"` (a tariff decision).
  `japanese/actors.json` has `"president": "社長"` (a company CEO, not a head
  of state) and `"cabinet": "キャビネット"` (the furniture). These are
  googletrans output and they silently break EPU matching.
- **Code-mix.** Many SSA, MENA and Asia-Pacific outlets mix English into
  otherwise non-English articles (especially for institution names and
  acronyms). The output must include English fallback strings so those
  passages still match.
- **Unsupported languages.** Arabic, Somali, Amharic, low-resource African
  languages have poor or no googletrans coverage. Claude gives consistent
  quality across all of them.

## Inputs

The user provides:

1. **Target language tag** — the same string used in the source YAML's
   `language:` field. It is also the folder name under
   `src/text/analysis/keywords/`. Examples seen in the repo: `fr`, `es`,
   `portuguese`, `swahili`, `somali`, `amharic`, `arabic`, `japanese`,
   `indo`, `vietnamese`, `tetum`. Do not invent a new tag — match what the
   YAML configs actually use. If you don't know, grep the configs first:
   `grep -r "^language:" src/text/configs/<region>/ | sort -u`.
2. **Which file(s)** — `epu`, `actors`, `topics`, or `all`. Default to `epu`
   if unstated, since `epu.json` is the only file required by the default
   `po text build` (the others only matter for `--additional <topic>` runs).

## Output format: array-of-variants

For every category in the English source, the output is an array of strings.
Each string is a candidate the matcher will look for in article bodies. The
array contains, in this order:

1. The canonical translation of the English term.
2. Common inflected/declined forms a news article would actually use:
   - Singular + plural
   - Definite + indefinite (for languages with articles, e.g. Arabic
     `اقتصاد`/`الاقتصاد`, Romance `economia`/`a economia` if the article
     genuinely fuses to the noun)
   - Masculine/feminine, where relevant
   - Adjective forms of nouns and vice versa where they're commonly used
3. Synonyms a journalist would naturally reach for. E.g. for "central bank"
   in Arabic both `البنك المركزي` and `المصرف المركزي`. For "government" in
   Spanish `gobierno` plus `gubernamental`/`administración`.
4. The original English term verbatim, plus any short English forms common in
   code-mix (acronyms, brand names). This catches English passages embedded
   in non-English articles.

The category keys (`economic`, `policy`, `uncertainty` for epu.json; `imf`,
`world_bank`, etc. for actors.json) come straight from the EN source — do not
rename or restructure. Only the values change.

### Canonical example (the gold standard)

`src/text/analysis/keywords/arabic/epu.json` is the reference. It expanded
the EN `economic` array from 5 items (`economy`, `economic`, `business`,
`finance`, `financial`) to 25 items by adding singular/plural/definite/
indefinite Arabic morphology and keeping the 5 English fallbacks. Read it
before you write.

### Worked schematic

EN source (`keywords/en/epu.json`):
```json
{ "economic": ["economy", "economic", "business", "finance", "financial"] }
```

Output for a hypothetical language with grammatical gender + definite article:
```json
{
  "economic": [
    "<canonical economy>",
    "<plural economies>",
    "<the-economy with article>",
    "<adjective economic, M>",
    "<adjective economic, F>",
    "<adjective economic, plural>",
    "<canonical business>",
    "<plural businesses>",
    "<synonym for business — commerce/trade>",
    "<canonical finance>",
    "<adjective financial, M>",
    "<adjective financial, F>",
    "economy", "economic", "business", "finance", "financial"
  ]
}
```

Aim for ~3–6 strings per English source term. The arabic file averages ~5.

## Proper nouns: keep verbatim

Do not translate these. They appear in news articles in their English form
across virtually every language. Same list as `PROPER_NOUNS` in
`src/text/analysis/translate_keywords.py:79-114`:

`IMF`, `IBRD`, `IDA`, `IFC`, `ADB`, `AFDB`, `IDB`, `EBRD`, `OECD`, `ILO`,
`WHO`, `WTO`, `UN`, `FDI`, `CPI`, `GDP`, `FOREX`, `S&P`, `PBOC`, `MOFCOM`,
`CPC`, `CCP`, `NDRC`, `USTR`, `MPS`, `COVID`, `COVID-19`, `Fitch`, `Moody's`,
`Standard & Poor's`.

You may *additionally* include a localized form if the language has an
official one used by national press (e.g. Arabic `صندوق النقد الدولي` for
IMF, Portuguese `FMI`, Spanish `Banco Mundial`). Both forms in the array.
Never replace the English with the localized one.

## Procedure

### 1. Read the English source

Always start by reading the actual EN file(s), not relying on memory:

- `src/text/analysis/keywords/en/epu.json` — 3 categories, 32 terms total
- `src/text/analysis/keywords/en/actors.json` — 17 categories, ~165 terms
- `src/text/analysis/keywords/en/topics.json` — 31 categories, ~430 terms

### 2. Read the canonical exemplar for tone

Read `src/text/analysis/keywords/arabic/epu.json`. Notice the depth (5 EN
terms → 25 Arabic strings), the morphological coverage, the inclusion of
English fallbacks at the end of each array. Match this density.

If working on actors/topics, also read
`src/text/analysis/keywords/arabic/actors.json` and
`src/text/analysis/keywords/arabic/topics.json` — same pattern, larger files.

### 3. Verify the language tag actually matches the YAMLs

```bash
grep -rh "^language:" src/text/configs/ | sort -u
```

Confirm the tag the user gave you appears here. If it doesn't, the keyword
file you generate will never be loaded — wrong tag means the EPU pipeline
silently falls back to English via `_resolve_keywords_dir`
(`src/text/analysis/utils.py:282-304`).

If there's an inconsistency (e.g. one YAML uses `language: ar` and three use
`language: arabic`), surface it to the user and ask which canonical form to
use. Do not silently create two folders.

### 4. Generate the translations

For each category in the EN source, expand each term per the rules above.
Work category-by-category — don't try to hold the whole file in your head at
once. For larger files (actors, topics), generate one category, sanity-check
it against the exemplar density, then proceed.

If the user asked for `all` but the file count is large (~600 terms for
actors+topics combined), generate them in sequence not in parallel — keeps
quality consistent.

### 5. Write the file

Path: `src/text/analysis/keywords/<lang>/<file>.json`

Format requirements:
- Valid UTF-8 JSON, `ensure_ascii=False`
- Two-space indent (matches the existing files)
- Trailing newline at end of file
- No comments, no extra metadata fields

If the directory doesn't exist, create it. If a file already exists, **do not
silently overwrite** — read it first and confirm with the user whether to
extend (merge new variants in) or replace.

### 6. Verify the file loads

Run both checks:

```bash
# Pure JSON parse
python -c "
import json
from pathlib import Path
for f in ['epu.json','actors.json','topics.json']:
    p = Path('src/text/analysis/keywords/<lang>') / f
    if p.exists():
        d = json.loads(p.read_text())
        cats = {k: len(v) for k,v in d.items()}
        print(f'{f}: {cats}')
"

# EPU pipeline loader (this is the real test — the loader is at
# src/text/analysis/epu.py:get_terms_for_language, NOT in utils.py)
PYTHONPATH=src poetry run python -c "
from text.analysis.epu import get_terms_for_language
t = get_terms_for_language('<lang>')
print({k: len(v) for k,v in t.items()})
"
```

Both must succeed. Term counts should be meaningfully larger than the EN
baseline (5/15/13 for epu) — if a category has the same count as EN, you
likely just translated each term once instead of producing variants.

### 7. Sanity check against the user's actual articles (optional but recommended)

If the user's goal is to unblock a build, after generating the file run:

```bash
poetry run po text status -S <subregion>
```

For sources in the new language, the per-source `epu_articles` count should
be non-zero. Zero matches across hundreds of articles indicates a quality
problem worth investigating — usually the translations are too formal or
miss a common synonym journalists actually use.

## Common pitfalls

- **Don't reuse the dict format.** `keywords/fr/`, `keywords/japanese/`, and
  the other older folders use `{english: translation}` per-term. That format
  works but loses recall. New languages always use the array format.
- **Don't drop the English fallback strings.** They're cheap and catch
  English-language passages and proper nouns inside non-English articles.
  Every category should end with the English source terms appended.
- **Don't translate proper nouns.** Keep `IMF`, `World Bank`, `Moody's`,
  `COVID-19` etc. exactly as written in PROPER_NOUNS.
- **Don't restructure the schema.** Categories must match the EN source 1:1
  by key. The pipeline iterates the whole dict — extra or renamed categories
  silently produce nothing.
- **Don't pile up hundreds of near-duplicate variants.** Quality > quantity.
  ~3–6 strings per English term is the right density for most languages.
  Languages with more inflection (Arabic, Russian-style) trend higher;
  languages with little morphology (Mandarin, Tok Pisin) trend lower.
- **Don't run `translate_keywords.py` "as a starting point" then fix.** The
  dict format and one-form-per-term limit mean you'd rewrite most of it
  anyway, and you'd be tempted to keep wrong-sense translations because
  they're already there.

## When to defer

Generating `actors.json` (~165 EN terms) and `topics.json` (~430 EN terms)
takes meaningful effort. If the user only needs `po text build --region X`
to run, only `epu.json` is required. Generate that first and confirm the
build works before investing in actors/topics. Topic-specific EPU runs
(`--additional <topic>`) are the only thing that loads `topics.json`.
