"""Layer-1 failure-mode diagnostics F1-F6 over the 313-row WORKING gold.

Scope (TMINE-05): for every gold row, decompose the product name into the six
MI components (`components.decompose`) and measure each component's mutual
information against the COICOP label using the `mi` backbone (bits, normalized
info-gain, permutation null). The report is organised as F1-F6:

- F1 wrong dimension  — dimension distribution per COICOP leaf; mixed leaves.
- F2 wrong net quantity — multiple-number-role ambiguity rate (residual input).
- F3 multipack/promo conflation — content + pack co-occurrence (residual input).
- F4 wrong category  — breadcrumb->leaf AND dimension->leaf info-gain.
- F5 non-comparable within leaf — within-leaf magnitude dispersion (CoV).
- F6 cross-language blindspot — per-language structural-span coverage.

Mutual information is reported at BOTH the full dotted COICOP leaf and a
4-digit-class truncation (`coicop_class`), in bits, alongside normalized
info-gain and a permutation-null floor — the small-sample-bias mitigation that
MUST stay visible because the gold is only 313 rows (RESEARCH Pitfall 3).

Every F-block is sliced by (language x COICOP division x channel); cells below
a small floor (`LOW_N_FLOOR`) are flagged "indicative, not estimable".

Read boundary: this module reads ONLY the 313-row working gold
(`gold_labels.parquet`). It NEVER reads the sealed held-out cert set.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from prices.enrich import config
from prices.enrich.text_mining import components, io, mi, report

GOLD_PARQUET = (
    config.REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "gold_labels.parquet"
)

# Below this row count an MI / dispersion cell is descriptive only, never a
# trustworthy estimate (the whole gold is 313 rows; per-slice cells are tiny).
LOW_N_FLOOR = 15

# Permutation-null sample count for the bias floor.
_NULL_N = 200
_RNG_SEED = 0

# Categorical components scored against the COICOP label.
_CATEGORICAL_COMPONENTS = ("brand", "identity_noun", "dimension", "pack", "breadcrumb")

_BIAS_CAVEAT = (
    "**Small-sample-bias caveat (n=313).** Plug-in mutual information is "
    "upward-biased on a small sample and the bias grows with a component's "
    "cardinality, so high-cardinality components (brand, identity-noun) look "
    "inflated relative to low-cardinality dimension / pack. Read raw MI ONLY "
    "alongside the **normalized info-gain** (MI / H(target), in [0,1]) and the "
    "**permutation-null** mean (the bias floor: target shuffled, MI recomputed) "
    "shown in each table. Do not treat a high raw MI as significance."
)


# --- COICOP code slicing ----------------------------------------------------


def coicop_class(code: str | None) -> str:
    """4-digit COICOP class = the first three dotted segments (e.g. 01.2.2).

    Gold codes are dotted (`01.2.2.0.1`, `13.1.2.0`); the 4-digit class per
    REQUIREMENTS is the division.group.class prefix — three dotted segments,
    four significant digits. Reported alongside the full leaf per RESEARCH
    Open Question 1.
    """
    if code is None:
        return ""
    parts = str(code).split(".")
    return ".".join(parts[:3])


def coicop_division(code: str | None) -> str:
    """COICOP division = the first dotted segment (e.g. 01)."""
    if code is None:
        return ""
    return str(code).split(".")[0]


# --- component decomposition over the gold ----------------------------------


def _decompose_gold(gold: pd.DataFrame) -> pd.DataFrame:
    """Augment the gold frame with the six components + COICOP class/division."""
    decomposed = [
        components.decompose(name, lang, None)
        for name, lang in zip(gold["product_name"], gold["language"], strict=False)
    ]
    out = gold.copy()
    for key in (
        "brand",
        "identity_noun",
        "dimension",
        "magnitude",
        "pack",
        "breadcrumb",
    ):
        out[f"comp_{key}"] = [d[key] for d in decomposed]
    out["coicop_class"] = [coicop_class(c) for c in gold["coicop_code_gold"]]
    out["coicop_division"] = [coicop_division(c) for c in gold["coicop_code_gold"]]
    return out


def _as_labels(values) -> list[str]:
    """Categorical components -> string labels (None -> "" so MI is defined)."""
    return ["" if v is None else str(v) for v in values]


# --- the MI backbone over the gold ------------------------------------------


def component_leaf_mi(gold: pd.DataFrame) -> list[dict]:
    """Per-component MI against the COICOP leaf AND 4-digit class, in bits.

    Returns one row per categorical component plus a continuous-magnitude row,
    each carrying raw MI (bits), normalized info-gain in [0,1], and the
    permutation-null mean (the bias floor) at both the leaf and the 4-digit
    class. n is the gold row count (flagged indicative below LOW_N_FLOOR).
    """
    dec = _decompose_gold(gold)
    leaf = list(dec["coicop_code_gold"])
    klass = list(dec["coicop_class"])
    rng = np.random.default_rng(_RNG_SEED)
    n = len(dec)
    rows: list[dict] = []

    for comp in _CATEGORICAL_COMPONENTS:
        x = _as_labels(dec[f"comp_{comp}"])
        _, null_leaf, _ = mi.mi_with_null(x, leaf, rng, n=_NULL_N)
        rows.append(
            {
                "component": comp,
                "mi_leaf_bits": round(mi.mi_bits(x, leaf), 4),
                "norm_info_gain_leaf": round(mi.normalized_info_gain(x, leaf), 4),
                "null_mean_leaf_bits": round(null_leaf, 4),
                "mi_class_bits": round(mi.mi_bits(x, klass), 4),
                "norm_info_gain_class": round(mi.normalized_info_gain(x, klass), 4),
                "n": n,
                "indicative": n < LOW_N_FLOOR,
            }
        )

    # Continuous magnitude vs categorical leaf / class (kNN estimator).
    mag = pd.to_numeric(dec["comp_magnitude"], errors="coerce").fillna(0.0).to_numpy()
    rows.append(
        {
            "component": "magnitude",
            "mi_leaf_bits": round(mi.mi_classif_bits(mag, leaf), 4),
            "norm_info_gain_leaf": "",
            "null_mean_leaf_bits": "",
            "mi_class_bits": round(mi.mi_classif_bits(mag, klass), 4),
            "norm_info_gain_class": "",
            "n": n,
            "indicative": n < LOW_N_FLOOR,
        }
    )
    return rows


def component_component_mi(corpus: pd.DataFrame) -> list[dict]:
    """Label-free component->component MI over a corpus-shaped frame, in bits.

    Reads raw surface (`product_name_original`) + per-row lang + category;
    decomposes each row and reports MI between component pairs that do not
    require the gold label (dimension->breadcrumb, dimension->pack,
    pack->breadcrumb). Never reads a COICOP label.
    """
    name_col = (
        "product_name_original"
        if "product_name_original" in corpus.columns
        else "product_name"
    )
    lang_col = "lang" if "lang" in corpus.columns else "language"
    cats = corpus["category"] if "category" in corpus.columns else [None] * len(corpus)
    decomposed = [
        components.decompose(name, lang, cat)
        for name, lang, cat in zip(
            corpus[name_col], corpus[lang_col], cats, strict=False
        )
    ]
    cols = {
        key: _as_labels(d[key] for d in decomposed)
        for key in ("dimension", "pack", "breadcrumb")
    }
    pairs = (("dimension", "breadcrumb"), ("dimension", "pack"), ("pack", "breadcrumb"))
    return [
        {
            "pair": f"{a} -> {b}",
            "mi_bits": round(mi.mi_bits(cols[a], cols[b]), 4),
            "n": len(corpus),
            "indicative": len(corpus) < LOW_N_FLOOR,
        }
        for a, b in pairs
    ]


# --- F4: category info-gain -------------------------------------------------


def f4_category(gold: pd.DataFrame) -> dict:
    """F4 wrong-category: breadcrumb->leaf AND dimension->leaf info-gain.

    Returns a dict keyed by component (breadcrumb, dimension) each with MI in
    bits at leaf + 4-digit class plus normalized info-gain in [0,1].
    """
    dec = _decompose_gold(gold)
    leaf = list(dec["coicop_code_gold"])
    klass = list(dec["coicop_class"])
    out: dict[str, dict] = {}
    for comp in ("breadcrumb", "dimension"):
        x = _as_labels(dec[f"comp_{comp}"])
        out[comp] = {
            "mi_leaf_bits": round(mi.mi_bits(x, leaf), 4),
            "norm_info_gain_leaf": round(mi.normalized_info_gain(x, leaf), 4),
            "mi_class_bits": round(mi.mi_bits(x, klass), 4),
            "norm_info_gain_class": round(mi.normalized_info_gain(x, klass), 4),
        }
    return out


# --- F1: dimension distribution per leaf ------------------------------------


def f1_dimension_per_leaf(gold: pd.DataFrame) -> list[dict]:
    """Per-leaf dimension distribution; flags mixed-dimension leaves."""
    dec = _decompose_gold(gold)
    rows: list[dict] = []
    for leaf, grp in dec.groupby("coicop_code_gold"):
        dims = [d for d in grp["comp_dimension"] if d]
        uniq = sorted(set(dims))
        rows.append(
            {
                "leaf": leaf,
                "n": len(grp),
                "dimensions": ", ".join(uniq) if uniq else "(none)",
                "mixed": len(uniq) > 1,
                "indicative": len(grp) < LOW_N_FLOOR,
            }
        )
    return rows


# --- F5: within-leaf magnitude dispersion -----------------------------------


def f5_within_leaf_dispersion(gold: pd.DataFrame) -> list[dict]:
    """Within-leaf magnitude coefficient of variation (non-comparable flag)."""
    dec = _decompose_gold(gold)
    dec["val"] = pd.to_numeric(dec.get("val_gold"), errors="coerce")
    rows: list[dict] = []
    for leaf, grp in dec.groupby("coicop_code_gold"):
        vals = grp["val"].dropna()
        mean = float(vals.mean()) if len(vals) else 0.0
        std = float(vals.std(ddof=0)) if len(vals) else 0.0
        cov = round(std / mean, 4) if mean else 0.0
        rows.append(
            {
                "leaf": leaf,
                "n": len(grp),
                "magnitude_cov": cov,
                "indicative": len(grp) < LOW_N_FLOOR,
            }
        )
    return rows


# --- F6: per-language structural-span coverage ------------------------------


def f6_language_coverage(gold: pd.DataFrame) -> list[dict]:
    """Per-language structural-span coverage (tier-a hit rate / residual)."""
    dec = _decompose_gold(gold)
    rows: list[dict] = []
    for lang, grp in dec.groupby("language"):
        has_span = grp["comp_dimension"].notna() & (grp["comp_dimension"] != "")
        covered = int(has_span.sum())
        rows.append(
            {
                "language": lang or "(none)",
                "n": len(grp),
                "span_covered": covered,
                "span_coverage": round(covered / len(grp), 4) if len(grp) else 0.0,
                "residual_share": round(1 - covered / len(grp), 4) if len(grp) else 0.0,
                "indicative": len(grp) < LOW_N_FLOOR,
            }
        )
    return rows


# --- F2 / F3: residual ambiguity inputs -------------------------------------


def f2_quantity_ambiguity(gold: pd.DataFrame) -> list[dict]:
    """F2 wrong-net-quantity: rows whose name carries multiple number tokens."""
    dec = _decompose_gold(gold)
    rows: list[dict] = []
    for _, r in dec.iterrows():
        digits = sum(
            tok.isdigit() or any(ch.isdigit() for ch in tok)
            for tok in str(r["product_name"]).split()
        )
        if digits > 1:
            rows.append(
                {
                    "product_name": r["product_name"],
                    "language": r["language"],
                    "number_tokens": digits,
                }
            )
    return rows


def f3_multipack_conflation(gold: pd.DataFrame) -> list[dict]:
    """F3 multipack/promo conflation: rows carrying a pack descriptor."""
    dec = _decompose_gold(gold)
    rows: list[dict] = []
    for _, r in dec.iterrows():
        if r["comp_pack"]:
            rows.append(
                {
                    "product_name": r["product_name"],
                    "language": r["language"],
                    "pack": r["comp_pack"],
                }
            )
    return rows


# --- slicing by language x division x channel -------------------------------


def slice_by_lang_division_channel(gold: pd.DataFrame) -> list[dict]:
    """Per-(language, division, channel) cell counts with the low-n flag.

    The gold has no channel column; channel falls back to "unknown" so the
    triple slice is still emitted (and flagged indicative on the tiny gold).
    """
    dec = _decompose_gold(gold)
    channel = (
        dec["channel"]
        if "channel" in dec.columns
        else pd.Series(["unknown"] * len(dec), index=dec.index)
    )
    dec = dec.assign(_channel=channel.fillna("unknown"))
    rows: list[dict] = []
    grouped = dec.groupby(["language", "coicop_division", "_channel"], dropna=False)
    for (lang, division, chan), grp in grouped:
        rows.append(
            {
                "language": lang or "(none)",
                "division": division or "(none)",
                "channel": chan or "unknown",
                "n": len(grp),
                "indicative": len(grp) < LOW_N_FLOOR,
            }
        )
    return rows


# --- Markdown assembly ------------------------------------------------------


def build_report(gold: pd.DataFrame, corpus: pd.DataFrame | None = None) -> str:
    """Assemble the F1-F6 Markdown report over the working gold.

    Always emits the small-sample-bias caveat. MI is reported at both the full
    leaf and the 4-digit class; every block carries the per-slice low-n flag.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts: list[str] = [
        report.md_section("Layer-1 Failure-Mode Diagnostics (F1-F6)", 1),
        f"_Generated {stamp} over {len(gold)} working-gold rows. "
        "Held-out cert set NOT read._",
        _BIAS_CAVEAT,
        report.md_section("Component -> COICOP MI backbone (leaf + 4-digit class)", 2),
        report.md_table(component_leaf_mi(gold)),
        report.md_section("Slices: language x COICOP division x channel", 2),
        report.md_table(slice_by_lang_division_channel(gold)),
        report.md_section("F1 wrong dimension — dimension distribution per leaf", 2),
        report.md_table(f1_dimension_per_leaf(gold)),
        report.md_section("F2 wrong net quantity — multiple-number-role rows", 2),
        report.md_table(f2_quantity_ambiguity(gold)),
        report.md_section("F3 multipack/promo conflation — pack-carrying rows", 2),
        report.md_table(f3_multipack_conflation(gold)),
        report.md_section("F4 wrong category — breadcrumb & dimension info-gain", 2),
        report.md_table(_f4_rows(f4_category(gold))),
        report.md_section("F5 non-comparable within leaf — magnitude CoV", 2),
        report.md_table(f5_within_leaf_dispersion(gold)),
        report.md_section("F6 cross-language blindspot — span coverage", 2),
        report.md_table(f6_language_coverage(gold)),
    ]
    if corpus is not None:
        parts.append(report.md_section("Label-free component -> component MI", 2))
        parts.append(report.md_table(component_component_mi(corpus)))
    return "\n\n".join(parts)


def _f4_rows(f4: dict) -> list[dict]:
    return [{"component": k, **v} for k, v in f4.items()]


def load_gold() -> pd.DataFrame:
    """Read the 313-row working gold. NEVER the sealed cert set."""
    return pd.read_parquet(GOLD_PARQUET)


def write_report(gold: pd.DataFrame | None = None, name: str = "failures.md") -> Path:
    """Render F1-F6 and write the Markdown report under the harness report dir."""
    if gold is None:
        gold = load_gold()
    return io.write_markdown(name, build_report(gold))
