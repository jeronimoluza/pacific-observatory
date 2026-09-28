"""Per-country and per-source lookups read from countries.yaml and the
per-source YAMLs, split out of prepare.py."""

from functools import lru_cache

import numpy as np
import pandas as pd

from core.config import load_countries


# These four walk countries.yaml and all 1,463 per-source YAMLs, which costs
# ~1.2s and does not depend on the frame being prepared. prepare_input called
# them on every invocation, which was free while it ran once over the whole
# corpus and is not once it runs per country.
@lru_cache(maxsize=1)
def _build_country_lang_map() -> dict[str, str]:
    """Country slug → first language from countries.yaml; '' if missing."""
    out: dict[str, str] = {}
    for slug, meta in load_countries().items():
        langs = meta.get("languages") or []
        out[slug] = langs[0] if langs else ""
    return out


@lru_cache(maxsize=1)
def _build_source_channel_map() -> dict[tuple[str, str], str]:
    """(country, source) → channel from per-source YAML; missing keys default
    to '' downstream."""
    from prices.config import PriceSourceConfig, discover_prices_configs

    out: dict[tuple[str, str], str] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        if cfg.channel:
            out[(cfg.country, cfg.source)] = cfg.channel
    return out


# Manifest spellings that are not language codes. A region suffix (zh-TW, fr-HT)
# reduces to its base code.
_LANG_NAMES = {"chinese_traditional": "zh", "portuguese": "pt"}


@lru_cache(maxsize=1)
def _build_source_lang_map() -> dict[tuple[str, str], str]:
    """(country, source) → language from per-source YAML, kept only when the
    regex registry has patterns for it. Other manifests are absent from the
    map, so their rows keep the countries.yaml value."""
    from prices.config import PriceSourceConfig, discover_prices_configs
    from prices.enrich.regex_patterns._registry import pattern_langs

    known = pattern_langs()
    out: dict[tuple[str, str], str] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        if not cfg.language:
            continue
        lang = _LANG_NAMES.get(cfg.language, cfg.language.split("-")[0])
        if lang in known:
            out[(cfg.country, cfg.source)] = lang
    return out

@lru_cache(maxsize=1)
def _build_source_coicop_codes_map() -> dict[tuple[str, str], str]:
    """(country, source) → `|`-joined declared coicop_codes from per-source
    YAML. Missing or empty declarations are absent from the map."""
    from prices.config import PriceSourceConfig, discover_prices_configs
    from prices.enrich.coicop_codes import serialize_codes

    out: dict[tuple[str, str], str] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        serialized = serialize_codes(cfg.coicop_codes)
        if serialized:
            out[(cfg.country, cfg.source)] = serialized
    return out


def _source_lookup(df: pd.DataFrame, mapping: dict, default: str = "") -> np.ndarray:
    """`(country, source)` -> `mapping` value, one dict lookup per DISTINCT pair.

    Replaces `df.set_index(["country", "source"]).index.map(lambda k: ...)`,
    which was two costs stacked: `set_index` rebuilt the whole frame -- every
    column, not just the two keys -- and `.map` then made one Python call per
    row, 110.3M of them per corpus pass, for an answer that only ever depends on
    the pair. `_derive` sees one country and a handful of sources at a time, so
    factorizing collapses those 110.3M lookups to a few dozen.

    `use_na_sentinel=False` keeps a null country or source as its own code
    rather than -1, so it stays a pair that simply misses the dict and takes
    `default` -- which is what `.get(k, default)` did with a NaN inside the
    tuple. The grid is countries x sources, and `_derive` sees one country, so
    it is a handful of cells; even a whole-corpus chunk is ~200 x ~1,100.
    """
    c_codes, countries = pd.factorize(df["country"], use_na_sentinel=False)
    s_codes, sources = pd.factorize(df["source"], use_na_sentinel=False)
    table = np.array(
        [[mapping.get((c, s), default) for s in sources] for c in countries],
        dtype=object,
    )
    return table[c_codes, s_codes]
