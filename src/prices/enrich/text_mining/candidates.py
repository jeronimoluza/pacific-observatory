"""Layer-2 candidate generation (TMINE-07) — HUMAN-REVIEW only.

Two emitters, both producing frequency/size-ranked Markdown for a human to
review and (manually, in a later phase) fold into the cascade:

- `tier_a_regex_candidates` mines the spine's *structural residuals* — rows the
  spine left WITHOUT a parseable structural span but that still carry a latent
  quantity/pack surface form (a digit + latin-unit-ish token the current tier-a
  regex missed). The residual surface forms are clustered and emitted ranked by
  frequency descending, each with a suggested regex sketch and example names.
- `tier_b_sublabel_candidates` clusters the canonical identity layer
  (products.parquet `first_name` / `canonical_loose`) within (country, channel)
  and emits candidate sub-labels ranked by cluster size descending.

HARD INVARIANT (T-007-18): this module writes NOTHING under
`regex_patterns/` or `tier_b/`. The sole write surface is `io.write_markdown`
under `io.REPORT_DIR`. Candidates are NOT auto-applied, registered, compiled, or
mutated into any cascade store. Regex sketches are human-reviewed *text*
(T-007-19): they are never compiled here, and avoid nested quantifiers.

Layer-2 ablation scoring against the held-out cert set is OUT OF SCOPE this
phase (deferred to Phase 1).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

import pandas as pd

from prices.enrich.text_mining import io
from prices.enrich.text_mining import report as md
from prices.enrich.text_mining.segment import segment_auto
from prices.enrich.text_mining.spine import split_spans

TIER_A_MARKDOWN_NAME = "candidates_tier_a_regex.md"
TIER_B_MARKDOWN_NAME = "candidates_tier_b_sublabels.md"

_NAME_COL = "product_name_original"

# Number of representative names to show per candidate cluster.
_MAX_EXAMPLES = 5

# A latent quantity/pack surface form the spine left unparsed: a run of digits
# glued (optionally) to a short latin token (kg, ml, pk, ct, gsm, oz, …). This
# is a DETECTION heuristic for residual mining only — it is never applied to the
# cascade and deliberately avoids nested quantifiers (T-007-19).
_LATENT_QTY = re.compile(r"\d+(?:\.\d+)?\s?[a-z]{1,4}\b", re.IGNORECASE)

# Stop tokens that carry no sub-label signal when clustering canonical names.
_STOP_TOKENS = frozenset({"the", "a", "an", "of", "and", "with", "for"})


def _latent_surfaces(name: str) -> list[str]:
    """Latent quantity/pack surface forms in a raw name, lower-cased."""
    if not isinstance(name, str):
        return []
    return [m.group(0).lower().replace(" ", "") for m in _LATENT_QTY.finditer(name)]


def _regex_sketch(surface_form: str) -> str:
    """A flat (no nested quantifiers) regex sketch for a residual surface form.

    Generalises the observed digits to ``\\d+`` and keeps the literal unit
    token, e.g. ``12pk`` -> ``\\d+pk``. Human-reviewed text only — never
    compiled or applied here.
    """
    unit = re.sub(r"^\d+(?:\.\d+)?", "", surface_form)
    unit = re.escape(unit)
    return rf"\d+(?:\.\d+)?{unit}" if unit else r"\d+(?:\.\d+)?"


def tier_a_regex_candidates(
    input_frame: pd.DataFrame,
    write: bool = False,
):
    """Frequency-ranked tier-a regex candidates from spine structural residuals.

    A residual is a row whose raw name the spine left WITHOUT a structural span
    (`has_structural_span` is False) yet that carries a latent quantity/pack
    surface form. The surface forms are counted across residuals and emitted
    ranked by frequency descending, each with a suggested regex sketch and up to
    `_MAX_EXAMPLES` example names.

    Returns `(rows, markdown)`. With `write=True`, also writes the Markdown under
    `io.REPORT_DIR` (only) and returns a dict with `rows`, `markdown`,
    `markdown_path`.
    """
    counts: Counter = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    if not input_frame.empty:
        langs = (
            input_frame["lang"]
            if "lang" in input_frame.columns
            else [None] * len(input_frame)
        )
        for name, lang in zip(input_frame[_NAME_COL], langs, strict=False):
            if not isinstance(name, str):
                continue
            if split_spans(name, lang)["has_structural_span"]:
                continue
            for surface in set(_latent_surfaces(name)):
                counts[surface] += 1
                if len(examples[surface]) < _MAX_EXAMPLES:
                    examples[surface].append(name)

    rows = [
        {
            "surface_form": surface,
            "count": count,
            "regex_sketch": _regex_sketch(surface),
            "example_names": "; ".join(examples[surface]),
        }
        for surface, count in counts.items()
    ]
    rows.sort(key=lambda r: (-r["count"], r["surface_form"]))

    markdown = _render_tier_a(rows)
    if not write:
        return rows, markdown
    markdown_path = io.write_markdown(TIER_A_MARKDOWN_NAME, markdown)
    return {"rows": rows, "markdown": markdown, "markdown_path": markdown_path}


def _cluster_key(name: str, canonical_loose) -> str | None:
    """A lightweight clustering key from sorted content tokens of the canonical
    identity layer — frequency/grouping, not a model train."""
    text = (
        canonical_loose
        if isinstance(canonical_loose, str) and canonical_loose
        else name
    )
    if not isinstance(text, str) or not text.strip():
        return None
    tokens = [t.lower() for t in segment_auto(text) if t.strip()]
    tokens = [t for t in tokens if t not in _STOP_TOKENS]
    if not tokens:
        return None
    return " ".join(sorted(set(tokens)))


def tier_b_sublabel_candidates(
    products_frame: pd.DataFrame,
    write: bool = False,
):
    """Size-ranked tier-b sub-label candidates from canonical-layer clustering.

    Clusters the canonical identity layer (`first_name` / `canonical_loose`)
    within (country, channel) by sorted content tokens and emits candidate
    sub-labels ranked by cluster size descending, each with up to `_MAX_EXAMPLES`
    representative names.

    Returns `(rows, markdown)`. With `write=True`, also writes the Markdown under
    `io.REPORT_DIR` (only) and returns a dict with `rows`, `markdown`,
    `markdown_path`.
    """
    clusters: dict[tuple, dict] = {}

    if not products_frame.empty:
        loose_col = (
            products_frame["canonical_loose"]
            if "canonical_loose" in products_frame.columns
            else [None] * len(products_frame)
        )
        channel_col = (
            products_frame["channel"]
            if "channel" in products_frame.columns
            else [None] * len(products_frame)
        )
        for name, loose, country, channel in zip(
            products_frame["first_name"],
            loose_col,
            products_frame["country"],
            channel_col,
            strict=False,
        ):
            key_text = _cluster_key(name, loose)
            if key_text is None:
                continue
            group = (str(country), str(channel), key_text)
            bucket = clusters.setdefault(
                group,
                {
                    "cluster_label": key_text,
                    "country": str(country),
                    "channel": str(channel),
                    "size": 0,
                    "_names": [],
                },
            )
            bucket["size"] += 1
            if isinstance(name, str) and len(bucket["_names"]) < _MAX_EXAMPLES:
                bucket["_names"].append(name)

    rows = [
        {
            "cluster_label": b["cluster_label"],
            "country": b["country"],
            "channel": b["channel"],
            "size": b["size"],
            "representative_names": "; ".join(b["_names"]),
        }
        for b in clusters.values()
    ]
    rows.sort(
        key=lambda r: (-r["size"], r["country"], r["channel"], r["cluster_label"])
    )

    markdown = _render_tier_b(rows)
    if not write:
        return rows, markdown
    markdown_path = io.write_markdown(TIER_B_MARKDOWN_NAME, markdown)
    return {"rows": rows, "markdown": markdown, "markdown_path": markdown_path}


_TIER_A_COLUMNS = ["surface_form", "count", "regex_sketch", "example_names"]
_TIER_B_COLUMNS = [
    "cluster_label",
    "country",
    "channel",
    "size",
    "representative_names",
]


def _render_tier_a(rows: list[dict]) -> str:
    parts = [
        md.md_section("Tier-A Regex Candidates (human review only)", 1),
        (
            "Frequency-ranked latent quantity/pack surface forms found in spine "
            "structural residuals — rows the spine left WITHOUT a structural "
            "span. Each `regex_sketch` is a SUGGESTION for a human to review; it "
            "is NOT compiled or applied to `regex_patterns/`. Ranked by `count` "
            "descending."
        ),
        md.md_section("Candidates", 2),
        md.md_table(rows, columns=_TIER_A_COLUMNS),
    ]
    return "\n\n".join(parts)


def _render_tier_b(rows: list[dict]) -> str:
    parts = [
        md.md_section("Tier-B Sub-Label Candidates (human review only)", 1),
        (
            "Size-ranked canonical-identity clusters within (country, channel). "
            "Each row is a CANDIDATE sub-label for a human to review; it is NOT "
            "written to `tier_b/`. Ranked by cluster `size` descending."
        ),
        md.md_section("Candidates", 2),
        md.md_table(rows, columns=_TIER_B_COLUMNS),
    ]
    return "\n\n".join(parts)
