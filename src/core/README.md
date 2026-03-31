# src/core/

Shared infrastructure used by all pipelines. Each module is small
(~20–60 lines) and serves at least two pipelines.

## Modules

| Module | Purpose | Used by |
|--------|---------|---------|
| `config.py` | Load countries.yaml, regions.yaml, settings.yaml; discover pipeline configs | All |
| `storage.py` | Per-source path helpers, country_slug(), CSV I/O | Fuel, prices |
| `state.py` | SourceState bookkeeping (.state.json), staleness assessment | All |
| `hashing.py` | SHA-256 observation hash for dedup | Fuel, prices |
| `http.py` | Default HTTP headers, make_session() | Fuel fetchers |
| `logging.py` | File logger setup: logs/{pipeline}/{region}/{country}/{source}/{date}/ | All |

## Design Principles

- No base classes or forced abstractions — just functions and TypedDicts
- Each module stands alone; no circular imports within core/
- Pipelines import what they need: `from core.state import read_state`
- Settings are loaded from `src/configs/` YAML files, not hardcoded
