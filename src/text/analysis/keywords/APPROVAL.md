# Keyword-Dictionary Approval Workflow

Every language directory under `keywords/` ships with a dictionary (`epu.json`, `topics.json`, `actors.json`) **and** a metadata file `_meta.json` that tracks provenance and approval status.

## Status ladder

Each `_meta.json` carries a `status` field with one of four values. Dictionaries move up the ladder as they're vetted:

| Status | Meaning | Allowed to use in … |
|---|---|---|
| `draft` | Translated from a source paper or machine-translated from English; unverified. | Experimentation only. Not for publication. |
| `reviewed` | One person (you, a native speaker, or the source paper's authors) has walked through the dictionary and confirmed the terms make sense. No manual precision audit yet. | Exploratory indices, internal dashboards. |
| `approved` | A precision audit has been run on ≥300 random articles flagged by the dictionary. Audit precision ≥ 0.75. Audit log recorded in `_meta.json`. | Research output, public index, reports. |
| `production` | Dictionary is `approved` AND is the live dictionary driving a published series. Only BBD English (and eventually the canonical UA dictionary) should ever reach this state. | Live published indices. |

Downgrade paths exist too — if a precision re-audit fails (e.g. corpus drift, new topic vocabulary like "sanctions 2022"), revert to `reviewed` or `draft` while the dictionary is updated.

## Promotion checklist

### `draft` → `reviewed`
- [ ] A native speaker or fluent second-language reader has read every term in `epu.json` and confirmed it's non-ambiguous and relevant.
- [ ] Cross-reference at least two known EPU spikes (e.g. 2014-03 Crimea for UA, 2020-03 COVID for all, 2022-02 invasion for UA/RU) — confirm the dictionary captures them when run against a sample.
- [ ] Update `_meta.json`: set `status=reviewed`, fill `last_review_date` and `reviewer`.

### `reviewed` → `approved`
- [ ] Run dictionary over the target country's newspaper panel for a 12-month test window.
- [ ] Sample 300 random articles flagged as EPU.
- [ ] Human-label each as `True` (genuinely about economic-policy uncertainty) or `False` (false positive). Ideally two labelers to check inter-rater agreement.
- [ ] Compute precision = `#True / 300`. Must be ≥ 0.75.
- [ ] Optional: recall — sample 300 random articles NOT flagged, label, count missed true EPU articles; target `recall ≥ 0.60`.
- [ ] Fill `audit` block in `_meta.json`: `sample_size`, `precision`, `recall`, `audit_date`, `audit_notes`. Set `status=approved`.

### `approved` → `production`
- [ ] The dictionary is used to publish a monthly index to `outputs/text/{region}/{country}/epu/`.
- [ ] Audit re-run annually; precision must remain ≥ 0.70.
- [ ] `status=production`.

Corpus / audit artifacts go under `outputs/text/audits/{lang}/{YYYY-MM-DD}/`, not the repo keyword dir.

## `_meta.json` schema

```json
{
  "language": "polish",
  "iso_codes": ["pl"],
  "status": "draft | reviewed | approved | production",
  "source": "full bibliographic reference",
  "source_url": "https://…",
  "source_table": "Table or appendix reference",
  "newspapers_used_by_source": ["…"],
  "standardization_period": "YYYY-MM to YYYY-MM",
  "notes": "free-form notes explaining translation choices",
  "audit": {
    "sample_size": 0,
    "precision": null,
    "recall": null,
    "audit_date": null,
    "audit_notes": ""
  },
  "last_review_date": null,
  "reviewer": null
}
```

## Current ECA coverage snapshot — 2026-04-24

| Language | Status | Source |
|---|---|---|
| English (`en`) | `production` | BBD 2016 canonical |
| Ukrainian (`ukrainian`) | `reviewed` | Repo in-house translation; awaiting precision audit |
| Polish (`polish`) | `draft` | Białkowski, Klepka & Sławik (2024), Table 1 — verbatim |
| Croatian (`croatian`) | `draft` | Sorić & Lolić (2017), Appendix 1 — verbatim + HR equivalents |
| Russian (`russian`) | `draft` | BBD (2016) Appendix A (Kommersant) — verbatim (Cyrillic restored) |
| Turkish (`turkish`) | `draft` | Provisional template (ECSU paper paywalled) |
| Belarusian (`belarusian`) | `draft` | Template translation |
| Romanian (`romanian`) | `draft` | Template translation — covers RO + MD |
| Bulgarian (`bulgarian`) | `draft` | Template translation |
| Serbian (`serbian`) | `draft` | Template translation (Cyrillic + Latin variants) |
| Bosnian (`bosnian`) | `draft` | Template translation |
| Albanian (`albanian`) | `draft` | Template translation — covers AL + XK |
| Macedonian (`macedonian`) | `draft` | Template translation |
| Armenian (`armenian`) | `draft` | Template translation |
| Azerbaijani (`azerbaijani`) | `draft` | Template translation |
| Georgian (`georgian`) | `draft` | Template translation |
| Kazakh (`kazakh`) | `draft` | Template translation |
| Kyrgyz (`kyrgyz`) | `draft` | Template translation |
| Uzbek (`uzbek`) | `draft` | Template translation (Latin script) |
| Tajik (`tajik`) | `draft` | Template translation (Cyrillic script) |
| Turkmen (`turkmen`) | `draft` | Template translation (Latin script) |
| Estonian (`estonian`) | `draft` | Template translation |
| Latvian (`latvian`) | `draft` | Template translation |
| Lithuanian (`lithuanian`) | `draft` | Template translation |

**All 21 ECA countries now have at least one language dictionary available** (via each country's native language and/or Russian for the Russian-language press in CIS countries).

The four countries with a directly-derived-from-published-source dictionary — Poland, Croatia, Russia, Türkiye (provisional) — can advance to `reviewed` with a single native-speaker walk-through. The 14 template-translated dictionaries all need a native-speaker pass to correct false-friends, inflections, and local terminology (e.g. actual NBU/NBK/NBS abbreviations, local parliament names).

## Minimum viable audit protocol (copy-pastable)

```python
# Run EPU matching over a panel for one year, sample 300 flagged articles
import random
from src.text.analysis.epu import run_epu_for_country

hits = run_epu_for_country(country="poland", language="polish",
                           start="2023-01", end="2023-12",
                           return_article_level=True)
hits_flagged = hits[hits["is_epu"]]
sample = hits_flagged.sample(300, random_state=42)
sample[["date", "paper", "title", "url"]].to_csv(
    "outputs/text/audits/polish/2026-04-24/sample.csv", index=False)

# Then label by hand in a spreadsheet — add a `label` column (1=true EPU, 0=false).
# Compute precision and paste into keywords/polish/_meta.json > audit.
```

## One-page "why each state exists"

- **draft**: caution flag — dictionary may contain literal typos, wrong inflections, false friends, or missing acronyms. Index results are illustrative.
- **reviewed**: at least the terms aren't nonsense. Useful for internal exploration.
- **approved**: defensible in a paper / public report. If someone asks "does this term really mean X?" you have a documented audit to point at.
- **production**: highest bar — you're willing to stake the repo's reputation on this dictionary being correct.
