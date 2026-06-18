"""Layer-0 corpus probe (TMINE-02) — "what am I even processing?"

Composes io + script_detect + language_id + segment + spine into a sliced
descriptive report over the raw-surface, type-level (unweighted) unique-item
corpus. Every stat block is produced both overall and sliced by country ×
channel. Stats are type-level by default (one count per unique row); the
optional `weighted=True` mode multiplies per-row contributions by `n_rows` and
exists only for the explicit weighted exception (RESEARCH Anti-pattern:
occurrence-weighting Layer-0 by default).

Reads `product_name_original` from products_input.parquet via io — never
`canonical_strict`. Persists `layer0_corpus_probe.md` under the harness report
dir via io.write_markdown (the sole write surface; asserts the boundary).
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from prices.enrich.text_mining import io, report
from prices.enrich.text_mining.language_id import detect_languages
from prices.enrich.text_mining.script_detect import char_script, dominant_script
from prices.enrich.text_mining.segment import collocations, ngrams, segment_auto
from prices.enrich.text_mining.spine import structural_span_density

_NAME_COL = "product_name_original"
_WEIGHT_COL = "n_rows"
_REPORT_NAME = "layer0_corpus_probe.md"
_TOP_N = 15
_CHAR_TOP_N = 10
_NGRAM_N = 2

REQUIRED_SECTIONS = [
    "Script Distribution",
    "Character Frequency",
    "Language Distribution",
    "Length Distributions",
    "Structural-Span Density",
    "Word / N-gram / Collocation",
]


def _weights(frame: pd.DataFrame, weighted: bool) -> list[int]:
    if weighted and _WEIGHT_COL in frame.columns:
        return [int(w) if pd.notna(w) else 1 for w in frame[_WEIGHT_COL]]
    return [1] * len(frame)


def _names(frame: pd.DataFrame) -> list[str]:
    return ["" if pd.isna(n) else str(n) for n in frame[_NAME_COL]]


def _share_rows(
    counter: Counter, key_name: str, top_n: int | None = None
) -> list[dict]:
    total = sum(counter.values())
    if total == 0:
        return []
    items = counter.most_common(top_n) if top_n else sorted(counter.items())
    return [
        {key_name: k, "count": int(c), "share": round(c / total, 6)} for k, c in items
    ]


def _script_distribution(names: list[str], weights: list[int]) -> list[dict]:
    counter: Counter = Counter()
    for name, w in zip(names, weights, strict=True):
        if name.strip():
            counter[dominant_script(name)] += w
    return _share_rows(counter, "script")


def _per_script_char_frequency(names: list[str], weights: list[int]) -> list[dict]:
    per_script: dict[str, Counter] = {}
    for name, w in zip(names, weights, strict=True):
        for char in name:
            per_script.setdefault(char_script(char), Counter())[char] += w
    rows: list[dict] = []
    for script in sorted(per_script):
        total = sum(per_script[script].values())
        for ch, c in per_script[script].most_common(_CHAR_TOP_N):
            rows.append(
                {
                    "script": script,
                    "char": ch,
                    "count": int(c),
                    "share": round(c / total, 6) if total else 0.0,
                }
            )
    return rows


def _language_distribution(names: list[str], weights: list[int]) -> list[dict]:
    langs = detect_languages(names)
    counter: Counter = Counter()
    for lang, w in zip(langs, weights, strict=True):
        counter[lang] += w
    return _share_rows(counter, "language")


def _length_dist(values: list[int], weights: list[int]) -> dict:
    if not values:
        return {"mean": 0.0, "min": 0, "max": 0, "p50": 0.0, "n": 0}
    series = pd.Series(values, dtype=float)
    wseries = pd.Series(weights, dtype=float)
    total_w = wseries.sum()
    mean = float((series * wseries).sum() / total_w) if total_w else 0.0
    expanded = series.repeat(wseries.astype(int)) if (wseries != 1).any() else series
    p50 = float(expanded.median()) if len(expanded) else 0.0
    return {
        "mean": round(mean, 4),
        "min": int(series.min()),
        "max": int(series.max()),
        "p50": round(p50, 4),
        "n": int(total_w),
    }


def _token_lengths(names: list[str]) -> list[int]:
    return [len(segment_auto(n)) for n in names if n.strip()]


def _char_lengths(names: list[str]) -> list[int]:
    return [len(n) for n in names if n.strip()]


def _word_top(names: list[str], weights: list[int]) -> list[dict]:
    counter: Counter = Counter()
    for name, w in zip(names, weights, strict=True):
        for tok in segment_auto(name):
            counter[tok] += w
    return _share_rows(counter, "word", top_n=_TOP_N)


def _ngram_top(names: list[str], weights: list[int]) -> list[dict]:
    counter: Counter = Counter()
    for name, w in zip(names, weights, strict=True):
        for gram in ngrams(segment_auto(name), _NGRAM_N):
            counter[" ".join(gram)] += w
    return _share_rows(counter, "ngram", top_n=_TOP_N)


def _collocation_top(names: list[str], weights: list[int]) -> list[dict]:
    counter: Counter = Counter()
    for name, w in zip(names, weights, strict=True):
        for gram, c in collocations(segment_auto(name), _NGRAM_N).items():
            counter[" ".join(gram)] += c * w
    return _share_rows(counter, "collocation", top_n=_TOP_N)


def _stat_for(frame: pd.DataFrame, weighted: bool) -> dict:
    names = _names(frame)
    weights = _weights(frame, weighted)
    return {
        "script_distribution": _script_distribution(names, weights),
        "per_script_char_frequency": _per_script_char_frequency(names, weights),
        "language_distribution": _language_distribution(names, weights),
        "token_length_dist": _length_dist(
            _token_lengths(names), _weights_nonblank(frame, weighted, names)
        ),
        "char_length_dist": _length_dist(
            _char_lengths(names), _weights_nonblank(frame, weighted, names)
        ),
        "structural_span_density": float(structural_span_density(frame)),
        "word_top": _word_top(names, weights),
        "ngram_top": _ngram_top(names, weights),
        "collocation_top": _collocation_top(names, weights),
    }


def _weights_nonblank(
    frame: pd.DataFrame, weighted: bool, names: list[str]
) -> list[int]:
    weights = _weights(frame, weighted)
    return [w for name, w in zip(names, weights, strict=True) if name.strip()]


_BLOCK_KEYS = [
    "script_distribution",
    "per_script_char_frequency",
    "language_distribution",
    "token_length_dist",
    "char_length_dist",
    "structural_span_density",
    "word_top",
    "ngram_top",
    "collocation_top",
]


def build_layer0_report(frame: pd.DataFrame, weighted: bool = False) -> dict:
    """Assemble every Layer-0 stat block, overall and sliced by country × channel.

    Type-level/unweighted by default; `weighted=True` multiplies per-row
    contributions by `n_rows` (the explicit weighted exception). Returns a dict
    keyed by block name; each block has an `overall` view and a
    `by_country_channel` view (dict keyed by (country, channel) tuples).
    """
    overall = _stat_for(frame, weighted)

    sliced: dict[str, dict] = {key: {} for key in _BLOCK_KEYS}
    if not frame.empty and "country" in frame.columns and "channel" in frame.columns:
        for key, group in frame.groupby(["country", "channel"], dropna=False):
            group_stat = _stat_for(group, weighted)
            for block in _BLOCK_KEYS:
                sliced[block][tuple(key)] = group_stat[block]

    return {
        block: {"overall": overall[block], "by_country_channel": sliced[block]}
        for block in _BLOCK_KEYS
    }


def _render_share_block(title: str, block: dict, key_name: str, level: int = 2) -> str:
    parts = [report.md_section(title, level)]
    parts.append(
        report.md_table(block["overall"], columns=[key_name, "count", "share"])
    )
    if block["by_country_channel"]:
        parts.append(
            report.md_slice_block(
                f"{title} — by country × channel",
                block["by_country_channel"],
                level=level + 1,
                columns=[key_name, "count", "share"],
            )
        )
    return "\n\n".join(parts)


def _render_length_block(title: str, token_block: dict, char_block: dict) -> str:
    parts = [report.md_section(title, 2)]
    parts.append(report.md_section("Token length", 3))
    parts.append(report.md_table([token_block["overall"]]))
    parts.append(report.md_section("Character length", 3))
    parts.append(report.md_table([char_block["overall"]]))
    if char_block["by_country_channel"]:
        rows = {k: [v] for k, v in char_block["by_country_channel"].items()}
        parts.append(
            report.md_slice_block(
                "Character length — by country × channel", rows, level=3
            )
        )
    return "\n\n".join(parts)


def _render_density_block(block: dict) -> str:
    parts = [report.md_section("Structural-Span Density", 2)]
    parts.append(f"Overall: {block['overall']:.4f}")
    rows = [
        {"country": k[0], "channel": k[1], "density": round(v, 4)}
        for k, v in block["by_country_channel"].items()
    ]
    if rows:
        parts.append(report.md_section("By country × channel", 3))
        parts.append(report.md_table(rows, columns=["country", "channel", "density"]))
    return "\n\n".join(parts)


def render(report_blocks: dict) -> str:
    parts = [report.md_section("Layer-0 Corpus Probe", 1)]
    parts.append(
        _render_share_block(
            "Script Distribution", report_blocks["script_distribution"], "script"
        )
    )
    parts.append(
        _render_share_block(
            "Character Frequency", report_blocks["per_script_char_frequency"], "char"
        )
    )
    parts.append(
        _render_share_block(
            "Language Distribution", report_blocks["language_distribution"], "language"
        )
    )
    parts.append(
        _render_length_block(
            "Length Distributions",
            report_blocks["token_length_dist"],
            report_blocks["char_length_dist"],
        )
    )
    parts.append(_render_density_block(report_blocks["structural_span_density"]))
    parts.append(
        _render_share_block(
            "Word / N-gram / Collocation", report_blocks["word_top"], "word"
        )
    )
    parts.append(
        _render_share_block("N-gram top", report_blocks["ngram_top"], "ngram", level=3)
    )
    parts.append(
        _render_share_block(
            "Collocation top", report_blocks["collocation_top"], "collocation", level=3
        )
    )
    return "\n\n".join(parts)


def run(weighted: bool = False):
    frame = io.read_products_input()
    report_blocks = build_layer0_report(frame, weighted=weighted)
    text = render(report_blocks)
    return io.write_markdown(_REPORT_NAME, text)
