"""Miners that feed the cascade's stores (boilerplate + the REVIEW flywheel).

  mine_source_boilerplate  per-source ubiquitous tokens (retailer/marketing words
                           that recur across most of a source's listings) ->
                           source_boilerplate.parquet. Conservative df-ratio gate
                           so real product nouns are never stripped.
  review_residue           parse the REVIEW reasons into candidate tokens, split
                           into brand/variety candidates vs OTHER base_items that
                           are confusing the cascade (report-back to base_items).
  confirm_varieties        human/oracle-confirmed variety tokens -> gazetteer as
                           benign (the flywheel step that shrinks REVIEW).
"""

from __future__ import annotations

import re

import pandas as pd

from .store import append_gazetteer, load_base_items, write_source_boilerplate

TOK = re.compile(r"[a-z]{3,}")
_RESIDUE = re.compile(r"^(brand-residue|no-cue|species-trap|form|neg):([a-z]+)")


def mine_source_boilerplate(
    rows: pd.DataFrame,
    name_col: str = "product_name_original",
    source_col: str = "source",
    lang_col: str = "lang",
    min_df_ratio: float = 0.4,
    min_products: int = 50,
) -> pd.DataFrame:
    """A token appearing in >= min_df_ratio of a source's product names is
    treated as that source's boilerplate. Writes source_boilerplate.parquet."""
    out = []
    for (source, lang), grp in rows.groupby([source_col, lang_col], dropna=False):
        names = grp[name_col].astype(str).str.lower().tolist()
        n = len(names)
        if n < min_products:
            continue
        df_count: dict[str, int] = {}
        for name in names:
            for tok in set(TOK.findall(name)):
                df_count[tok] = df_count.get(tok, 0) + 1
        for tok, c in df_count.items():
            if c / n >= min_df_ratio:
                out.append({"source": source, "language": lang, "text": tok})
    boiler = pd.DataFrame(out, columns=["source", "language", "text"])
    if not boiler.empty:
        write_source_boilerplate(boiler)
    return boiler


def review_residue(result: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """From cascade output (columns: reason, decision), split REVIEW residue into
    (candidate brand/variety tokens, OTHER base_items to report back)."""
    rev = result[result["decision"] == "REVIEW"]
    counts: dict[str, int] = {}
    for reason in rev["reason"].astype(str):
        m = _RESIDUE.match(reason)
        if m:
            counts[m.group(2)] = counts.get(m.group(2), 0) + 1
    residue = pd.DataFrame(
        sorted(counts.items(), key=lambda kv: -kv[1]), columns=["token", "n"]
    )

    known = set(load_base_items()["base_item"].astype(str).str.lower())
    known |= set(load_base_items()["base_name"].astype(str).str.lower())
    cross = residue[residue["token"].isin(known)].reset_index(drop=True)
    candidates = residue[~residue["token"].isin(known)].reset_index(drop=True)
    return candidates, cross


def confirm_varieties(base_item: str, tokens: list[str]) -> None:
    """Confirmed cultivar/brand tokens -> gazetteer benign (flywheel)."""
    append_gazetteer(
        base_item,
        {t.lower(): ("variety", "flywheel:confirmed") for t in tokens},
    )
