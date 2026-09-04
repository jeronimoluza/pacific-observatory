"""Per-leaf COICOP division-01 support table (the support-driven-scraping worklist).

Widens MISSING_CODES.md from the 85 *absent* leaves to all 269 division-01
leaves, joins observation/label counts onto every leaf, carries the
MISSING_CODES.md reason taxonomy forward, and reverse-ranks the reachable leaves
by support so the tail becomes an onboarding worklist. Re-runnable after any
rebuild — the whole point is to show movement between scraping cycles.

Artifacts read (state them on the table — see `ARTIFACTS`):
  - taxonomy    data/prices/enrich/coicop_categories.xlsx  (269 leaves + titles)
  - classified  data/prices/enrich/cache/classified.parquet (what the clf emits)
  - observations data/prices/build/global_prices_observations.parquet
  - trusted     data/prices/build/global_prices_trusted_observations.parquet (ships)
  - gold        data/prices/enrich/gold/gold_labels.parquet (the file the head
                trainer actually reads via classifier.dataset._load_gold; count
                verdict=="leaf" — NOT keyword matching, which lies, see brief)

Emits leaf_support_table.{csv,parquet,xlsx} + a regenerated Markdown view under
outputs/prices/leaf_support/.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data" / "prices"
TAX_XLSX = DATA / "enrich" / "coicop_categories.xlsx"
CLASSIFIED = DATA / "enrich" / "cache" / "classified.parquet"
OBS = DATA / "build" / "global_prices_observations.parquet"
TRUSTED = DATA / "build" / "global_prices_trusted_observations.parquet"
GOLD = DATA / "enrich" / "gold" / "gold_labels.parquet"
MISSING_MD = REPO_ROOT / "MISSING_CODES.md"
# Committed corpus-verification overlay (58 hand-verified absent leaves). Lives
# under src/ — NOT outputs/ — so the generator reproduces from a clean checkout.
VERIFY_CSV = Path(__file__).resolve().parent / "leaf_verification_div01.csv"
OUT_DIR = REPO_ROOT / "outputs" / "prices" / "leaf_support"

ARTIFACTS = {
    "taxonomy": str(TAX_XLSX.relative_to(REPO_ROOT)),
    "classified": str(CLASSIFIED.relative_to(REPO_ROOT)),
    "observations": str(OBS.relative_to(REPO_ROOT)),
    "trusted": str(TRUSTED.relative_to(REPO_ROOT)),
    "gold": str(GOLD.relative_to(REPO_ROOT)),
}

# MISSING_CODES.md section header -> failure_mode value for absent leaves.
_SECTION_MODE = {
    "Sourcing gap": "sourcing_gap",
    "Not in EAP retail": "out_of_region",
    "Catch-all": "catch_all",
    "Out of scope": "out_of_scope",
}
# Reachability: catch_all + out_of_scope are unreachable by design; out_of_region
# is reachable only under basket/region expansion (flagged separately).
_UNREACHABLE = {"catch_all", "out_of_scope"}


def _div01_leaves(tax: pd.DataFrame) -> set[str]:
    codes = set(tax["code"].astype(str).str.strip())
    div01 = {c for c in codes if c.startswith("01")}
    return {
        c for c in div01 if not any(o != c and o.startswith(c + ".") for o in div01)
    }


def _rollup(code: str) -> dict:
    p = code.split(".")
    return {
        "division": p[0],
        "group": ".".join(p[:2]),
        "class": ".".join(p[:3]),
        "subclass": ".".join(p[:4]),
    }


def _present(path: Path, leaves: set[str]) -> pd.Series:
    d = pd.read_parquet(path, columns=["coicop_code"])
    s = d["coicop_code"].dropna().astype(str).str.strip()
    return s[s.isin(leaves)].value_counts()


def _parse_missing(md: str) -> dict[str, dict]:
    """code -> {failure_mode, reason} parsed from the four MISSING_CODES.md tables."""
    out: dict[str, dict] = {}
    mode = None
    row_re = re.compile(r"^\|\s*`([^`]+)`\s*\|([^|]*)\|(.*)\|\s*$")
    for line in md.splitlines():
        if line.startswith("## "):
            head = line[3:].strip()
            mode = next(
                (v for k, v in _SECTION_MODE.items() if head.startswith(k)), None
            )
            continue
        if mode is None:
            continue
        m = row_re.match(line)
        if m:
            out[m.group(1).strip()] = {
                "failure_mode": mode,
                "reason": m.group(3).strip(),
            }
    return out


def _trusted_gap_reasons(gap: list[str]) -> dict[str, str]:
    """Diagnose why each observed-but-untrusted leaf falls out, from its own
    qa_status mix — not a guess. All-review_missing_qty leaves are the item /
    sold_by_item quarantine (no resolvable quantity -> no unit value)."""
    obs = pd.read_parquet(OBS, columns=["coicop_code", "qa_status"])
    obs["coicop_code"] = obs["coicop_code"].astype(str).str.strip()
    reasons = {}
    for code in gap:
        sub = obs[obs["coicop_code"] == code]
        vc = sub["qa_status"].value_counts()
        top, n = vc.index[0], int(vc.iloc[0])
        pct = round(100 * n / len(sub))
        if top == "review_missing_qty":
            why = (
                "item / sold_by_item quarantine — no resolvable quantity, so no unit "
                "value; fix is the sold_by_item allowlist or quantity recovery, not fx/uv"
            )
        elif top == "review_uv_outlier":
            why = "all rows fail the unit-value sanity check (log-MAD outlier)"
        elif top == "review_fx":
            why = "all rows lack an fx rate for the observation date"
        elif top == "review_zero_price":
            why = "all rows have non-positive price"
        else:
            why = f"all rows held at qa_status={top}"
        reasons[code] = f"{pct}% {top} ({len(sub)} obs) — {why}"
    return reasons


def build_table() -> pd.DataFrame:
    tax = pd.read_excel(TAX_XLSX)
    leaves = _div01_leaves(tax)
    titles = (
        tax.assign(code=tax["code"].astype(str).str.strip())
        .drop_duplicates("code")
        .set_index("code")["title"]
    )

    n_cls = _present(CLASSIFIED, leaves)
    n_obs = _present(OBS, leaves)
    n_tru = _present(TRUSTED, leaves)
    if set(n_cls.index) != set(n_obs.index):
        raise AssertionError("classified and observations leaf sets differ")

    tru = pd.read_parquet(TRUSTED, columns=["coicop_code", "country"])
    tru["coicop_code"] = tru["coicop_code"].astype(str).str.strip()
    n_ctry = (
        tru[tru["coicop_code"].isin(leaves)].groupby("coicop_code")["country"].nunique()
    )

    gold = pd.read_parquet(GOLD, columns=["code", "verdict"])
    gold["code"] = gold["code"].astype(str).str.strip()
    n_lab = gold[(gold["verdict"] == "leaf") & gold["code"].isin(leaves)][
        "code"
    ].value_counts()

    missing = _parse_missing(MISSING_MD.read_text(encoding="utf-8"))
    gap6 = sorted(set(n_obs.index) - set(n_tru.index))
    gap_reasons = _trusted_gap_reasons(gap6)

    rows = []
    for code in sorted(leaves):
        rec = {"coicop_leaf": code, "title": titles.get(code, ""), **_rollup(code)}
        rec["n_obs_classified"] = int(n_cls.get(code, 0))
        rec["n_obs_observations"] = int(n_obs.get(code, 0))
        rec["n_obs_trusted"] = int(n_tru.get(code, 0))
        rec["n_countries_trusted"] = int(n_ctry.get(code, 0))
        rec["n_labeled"] = int(n_lab.get(code, 0))

        # Presence wins over the static MISSING_CODES.md list: a leaf that now
        # carries observations has moved out of "absent", even if it is still
        # listed there (that is exactly the movement this table exists to show —
        # e.g. leaves recovered by a gold-labeling round + re-classify).
        if code in missing and rec["n_obs_observations"] == 0:  # still absent
            rec["failure_mode"] = missing[code]["failure_mode"]
            rec["reason"] = missing[code]["reason"]
        elif code in gap_reasons:  # observed but does not ship
            rec["failure_mode"] = "trusted_tier"
            rec["reason"] = gap_reasons[code]
        elif code in missing:  # was in MISSING_CODES, now recovered into the build
            rec["failure_mode"] = "ok"
            rec["reason"] = (
                "recovered — listed in MISSING_CODES but now classified into the build"
            )
        elif rec["n_obs_observations"] == 0:  # empty, and NOT catalogued as absent
            rec["failure_mode"] = "dropped"
            rec["reason"] = (
                "0 observations and not in MISSING_CODES — coverage lost this cycle or uncatalogued"
            )
        else:  # ships
            rec["failure_mode"] = "ok"
            rec["reason"] = ""

        mode = rec["failure_mode"]
        rec["reachable"] = mode not in _UNREACHABLE
        rec["out_of_region"] = mode == "out_of_region"
        rec["reachable_current_scope"] = rec["reachable"] and not rec["out_of_region"]
        rows.append(rec)

    df = pd.DataFrame(rows)

    # Corpus-verification overlay. 7 agents hand-checked all 58 out_of_region +
    # sourcing_gap absent leaves against products_input: genuine SKU counts, the
    # real bottleneck (sourcing / gold_labeling / true_absence), and a corrected
    # failure_mode where the corpus disagrees with MISSING_CODES. The original
    # failure_mode is kept for provenance; failure_mode_verified is the corrected
    # routing signal, and bottleneck splits the "empty" state 3 ways.
    ver = pd.read_csv(VERIFY_CSV, dtype={"coicop_leaf": str})
    df = df.merge(
        ver[
            [
                "coicop_leaf",
                "n_corpus_candidates",
                "verdict",
                "failure_mode_verified",
                "bottleneck",
                "misrouted_to",
            ]
        ],
        on="coicop_leaf",
        how="left",
    )
    df["failure_mode_verified"] = df["failure_mode_verified"].fillna(df["failure_mode"])
    for col in ("verdict", "bottleneck", "misrouted_to"):
        df[col] = df[col].fillna("")
    df["n_corpus_candidates"] = df["n_corpus_candidates"].astype("Int64")

    # priority_rank: ascending support over the currently-scoped reachable set
    # (216). Least support -> rank 1 (most urgent worklist item).
    work = df[df["reachable_current_scope"]].copy()
    work = work.sort_values(
        ["n_obs_trusted", "n_obs_observations", "n_labeled", "coicop_leaf"]
    ).reset_index()
    ranks = {r["coicop_leaf"]: i + 1 for i, r in work.iterrows()}
    df["priority_rank"] = df["coicop_leaf"].map(ranks).astype("Int64")
    return df.sort_values("coicop_leaf").reset_index(drop=True)


def _check(df: pd.DataFrame) -> None:
    # Invariants, not a frozen snapshot — this table is re-run every cycle to show
    # movement, so absolute counts (trusted>0, per-mode) are expected to drift.
    assert len(df) == 269, f"expected 269 leaves, got {len(df)}"
    assert df["coicop_leaf"].is_unique, "duplicate leaves"
    counts = df["failure_mode"].value_counts().to_dict()
    assert set(counts) <= {
        "ok",
        "sourcing_gap",
        "out_of_region",
        "catch_all",
        "out_of_scope",
        "trusted_tier",
        "dropped",
    }, counts

    # Presence wins: every non-shipping mode (catalogued-absent or dropped) must
    # carry zero observations; trusted_tier is the only zero-trusted mode with obs.
    empty_modes = (
        "sourcing_gap",
        "out_of_region",
        "catch_all",
        "out_of_scope",
        "dropped",
    )
    assert (
        int(df[df["failure_mode"].isin(empty_modes)]["n_obs_observations"].sum()) == 0
    ), "empty-mode leaf has observations"
    # `ok` is exactly the set that ships into the trusted build.
    assert set(df.loc[df["failure_mode"] == "ok", "coicop_leaf"]) == set(
        df.loc[df["n_obs_trusted"] > 0, "coicop_leaf"]
    ), "ok must equal the shipping set"
    # Static design buckets — unreachable by construction, independent of the data.
    assert counts.get("catch_all") == 20, counts
    assert counts.get("out_of_scope") == 7, counts

    # Overlay: all 58 verified absent leaves carry the verification columns. The
    # corrected routing splits out_of_region 13 / sourcing_gap 45 — a historical
    # routing decision keyed to the overlay, NOT the current failure_mode (5
    # gold_labeling leaves have since been recovered by round-14 and now ship).
    ver = df[df["n_corpus_candidates"].notna()]
    assert len(ver) == 58, "overlay must cover 58 leaves"
    assert df["failure_mode_verified"].notna().all(), (
        "failure_mode_verified must be total"
    )
    vc = ver["failure_mode_verified"].value_counts().to_dict()
    assert vc.get("sourcing_gap") == 45, vc
    assert vc.get("out_of_region") == 13, vc
    assert set(df.loc[df["bottleneck"] != "", "bottleneck"]) == {
        "sourcing",
        "gold_labeling",
        "true_absence",
    }, "bottleneck enum"


def _markdown(df: pd.DataFrame) -> str:
    n_tru = int((df["n_obs_trusted"] > 0).sum())
    scope = int(df["reachable_current_scope"].sum())
    lines = [
        "# COICOP division-01 leaf support table",
        "",
        f"Coverage: **{n_tru}/{scope} = {round(100 * n_tru / scope)}%** of currently-scoped "
        "reachable leaves ship into the trusted build.",
        "",
        "Artifacts: "
        + ", ".join(f"`{k}`=`{v}`" for k, v in ARTIFACTS.items())
        + ". `n_labeled` counts `verdict=='leaf'` rows in the gold file the head trainer reads.",
        "",
        "Corpus-verification overlay (`src/prices/build/leaf_verification_div01.csv`): "
        "all 58 `out_of_region`/`sourcing_gap` absent leaves were hand-checked against "
        "`products_input` (2 re-corrected after a round-14 sibling-leaf def-check). "
        "`failure_mode_verified` corrects the split (out_of_region 26→13, "
        "sourcing_gap 32→45); `bottleneck` splits the empty state into **sourcing** "
        "(40, more crawlers), **gold_labeling** (5, SKUs exist but no gold → classifier "
        "can't emit), **true_absence** (13, genuinely 0 or covered on a sibling leaf — "
        "skip). `n_corpus_candidates` "
        "is the genuine SKU count; `misrouted_to` flags leaves whose SKUs land on a wrong "
        "neighbor.",
        "",
        "## Failure-mode summary",
        "",
        "| failure_mode | leaves | reachable |",
        "| --- | ---: | --- |",
    ]
    reach = df.groupby("failure_mode")["reachable_current_scope"].first()
    for mode, n in df["failure_mode"].value_counts().items():
        lines.append(f"| {mode} | {n} | {'yes' if reach[mode] else 'no'} |")
    lines += [
        "",
        "## Worklist — reachable leaves by ascending support (top 40)",
        "",
        "| rank | leaf | title | trusted | obs | labeled | failure_mode |",
        "| ---: | --- | --- | ---: | ---: | ---: | --- |",
    ]
    top = df[df["priority_rank"].notna()].sort_values("priority_rank").head(40)
    for _, r in top.iterrows():
        lines.append(
            f"| {int(r['priority_rank'])} | `{r['coicop_leaf']}` | {r['title']} | "
            f"{r['n_obs_trusted']} | {r['n_obs_observations']} | {r['n_labeled']} | {r['failure_mode']} |"
        )
    return "\n".join(lines) + "\n"


def run() -> dict:
    df = build_table()
    _check(df)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv = OUT_DIR / "leaf_support_table.csv"
    df.to_csv(csv, index=False)
    df.to_parquet(OUT_DIR / "leaf_support_table.parquet", index=False)
    df.to_excel(OUT_DIR / "leaf_support_table.xlsx", index=False)
    (OUT_DIR / "leaf_support_table.md").write_text(_markdown(df), encoding="utf-8")
    return {
        "csv": str(csv),
        "n_leaves": len(df),
        "n_trusted": int((df["n_obs_trusted"] > 0).sum()),
        "reachable_current_scope": int(df["reachable_current_scope"].sum()),
    }


if __name__ == "__main__":
    print(run())
