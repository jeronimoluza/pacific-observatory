# Shared Pipeline

`src/` is organized around a shared pipeline language even when each area has its own local implementation. The goal is to let people talk about the work with a small set of stage names before they need to know internal module names.

## The Stages

| Stage | What it means | Typical artifacts |
| --- | --- | --- |
| `collect` | Acquire source material with minimal irreversible transformation. Preserve provenance and source evidence. | Raw HTML, JSONL, CSV, RSS pulls, logs, snapshots, source metadata |
| `normalize` | Turn source-specific outputs into comparable structures with stable ids, dates, paths, and schemas. | Canonical tables, cleaned columns, harmonized dates, source and country keys |
| `enrich` | Add information that does not exist directly in the source but matters downstream. | COICOP codes, unit values, quality flags, keyword tags, derived text features |
| `analyze` | Build indicators, reports, or analytical tables from normalized and enriched data. | EPU series, CPI tables, comparison outputs, summaries |
| `publish` | Produce human-facing or downstream-facing deliverables. | HTML dashboards, plots, CSV exports, shareable reports |

## What The Stages Mean In Practice

### `collect`

Collect is about getting source material into the repository's working data flow without losing traceability. That includes newspaper articles, retailer price snapshots, Wayback captures, fuel downloads, RSS pulls, and similar source evidence.

### `normalize`

Normalize is where source-specific quirks get turned into stable structures. This is where dates become consistent, identifiers become usable across runs, columns settle into repeatable schemas, and folder layouts become predictable enough for downstream stages.

### `enrich`

Enrich adds interpretation and structure that the raw source did not provide on its own. In this repo that includes things like COICOP classification, standardized unit extraction, quality flags, joins to reference data, and text-derived features that help downstream analysis.

### `analyze`

Analyze turns the working datasets into indicators and research outputs. This is where we build EPU-style text measures, CPI-style price indices, comparison tables, summaries, and other analytical artifacts.

### `publish`

Publish packages outputs for people who are not living inside the raw pipeline. That can mean HTML dashboards, plots, export tables, summary files, or other deliverables we want to inspect, share, or move toward production.

## How The Current Areas Map To The Pipeline

- `src/text/` - collect newspaper articles, normalize article records, enrich with text features and monitoring metadata, analyze EPU and related indicators, publish plots and dashboards.
- `src/cpi/` - collect retailer, wayback, and fuel data, normalize price tables, enrich with quantities and COICOP, analyze indices and comparison outputs, publish tables and visual artifacts.
- `src/tourism/` - collect tourism source data, normalize parsed records, enrich with joins or labels, analyze recovery and flow indicators, publish charts and tables.

## Checks

Each stage should have a cheap, local check:

- `collect` - did files arrive, did the run finish, do counts look sane?
- `normalize` - do schemas, ids, and dates line up with expectations?
- `enrich` - are derived fields populated at expected rates, and are fallbacks explicit?
- `analyze` - do outputs reproduce and pass quick sanity checks?
- `publish` - do generated artifacts render and point at current data?

We will document the shared check matrix in more detail later. For now, keep checks close to the local pipeline that owns them.
