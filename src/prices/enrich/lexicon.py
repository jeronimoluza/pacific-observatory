import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import click
import numpy as np
import pandas as pd

from prices.enrich import config, label_store
from prices.enrich.keys import norm_key

LEXICON_PATH = config.ENRICH_DIR / "lexicon.parquet"
LEXICON_MANIFEST_PATH = config.ENRICH_DIR / "lexicon_manifest.json"
PRODUCT_DECISIONS_CSV = (
    config.REPO_ROOT / "outputs" / "prices" / "validation" / "product_decisions.csv"
)

LEXICON_VERSION = "v0"
MIN_LEN = 3
MIN_COUNT = 20
MIN_CONTEXTS = 2

_STORE_LABEL = {
    "leaf": None,  # replaced by row["leaf"]
    "exclude": "__EXCLUDE__",
    "other_form": "__OTHER_FORM__",
}


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(config.REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _phrases(key: str):
    t = key.split()
    grams = set(t)
    grams |= {" ".join(t[i : i + 2]) for i in range(len(t) - 1)}
    return {g for g in grams if len(g) >= MIN_LEN}


def _resolved_decisions():
    d = pd.read_csv(PRODUCT_DECISIONS_CSV, dtype=str)
    d = d[d["decision"] != "REVIEW"].copy()
    d["key"] = d["product_name"].map(norm_key)
    d = d[d["key"].str.len() >= 2]
    d["label"] = np.where(
        d["decision"] == "GREEN",
        d["coicop_deep_leaf_code"],
        "__" + d["decision"] + "__",
    )
    prio = d["decision"].map({"GREEN": 0, "OTHER_FORM": 1, "EXCLUDE": 2})
    cnt = (
        d.assign(prio=prio)
        .groupby(["key", "label", "prio"], sort=False)
        .size()
        .reset_index(name="n")
        .sort_values(["key", "prio", "n"], ascending=[True, True, False])
    )
    resolved = cnt.drop_duplicates("key")[["key", "label"]].reset_index(drop=True)
    resolved["provenance"] = "decisions"

    ctx_code = (
        (d["country"].astype(str) + "\x1f" + d["source"].astype(str))
        .astype("category")
        .cat.codes
    )
    key_ctx: dict[str, set] = {}
    for key, code in zip(d["key"], ctx_code):
        key_ctx.setdefault(key, set()).add(int(code))
    return resolved, key_ctx


def _store_overrides(resolved: pd.DataFrame) -> pd.DataFrame:
    act = label_store.active()
    if act.empty:
        return resolved
    keep = act[act["decision"].isin(["leaf", "exclude", "other_form"])].copy()
    if keep.empty:
        return resolved

    def _lab(row):
        if row["decision"] == "leaf":
            return row["leaf"]
        return _STORE_LABEL[row["decision"]]

    keep["key"] = keep["canonical_key"]
    keep["label"] = keep.apply(_lab, axis=1)
    keep = keep[keep["label"].notna()][["key", "label"]]

    by_key = resolved.set_index("key")
    extra = []
    for _, r in keep.iterrows():
        if r["key"] in by_key.index:
            by_key.loc[r["key"], "label"] = r["label"]
            by_key.loc[r["key"], "provenance"] = "label_store"
        else:
            extra.append(
                {"key": r["key"], "label": r["label"], "provenance": "label_store"}
            )
    out = by_key.reset_index()
    if extra:
        out = pd.concat([out, pd.DataFrame(extra)], ignore_index=True)
    return out


def build_lexicon(path=LEXICON_PATH) -> pd.DataFrame:
    t0 = time.time()
    resolved, key_ctx = _resolved_decisions()
    resolved = _store_overrides(resolved)

    label_counts: dict[str, dict[str, int]] = {}
    label_ctx: dict[str, dict[str, set]] = {}
    for key, label in zip(resolved["key"], resolved["label"]):
        ctx = key_ctx.get(key, set())
        for ph in _phrases(key):
            lc = label_counts.setdefault(ph, {})
            lc[label] = lc.get(label, 0) + 1
            cx = label_ctx.setdefault(ph, {}).setdefault(label, set())
            cx |= ctx

    out_rows = []
    for ph, lc in label_counts.items():
        if len(lc) != 1:
            continue
        label = next(iter(lc))
        n = lc[label]
        n_contexts = len(label_ctx[ph][label])
        if n >= MIN_COUNT and n_contexts >= MIN_CONTEXTS:
            out_rows.append(
                {
                    "phrase": ph,
                    "label": label,
                    "n": n,
                    "purity": 1.0,
                    "n_contexts": n_contexts,
                    "provenance": "decisions+label_store",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "lexicon_version": LEXICON_VERSION,
                }
            )

    lex = pd.DataFrame(
        out_rows,
        columns=[
            "phrase",
            "label",
            "n",
            "purity",
            "n_contexts",
            "provenance",
            "created_at",
            "lexicon_version",
        ],
    )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lex.to_parquet(p, index=False)

    manifest = {
        "lexicon_version": LEXICON_VERSION,
        "code_version": _git_sha(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "params": {
            "min_len": MIN_LEN,
            "min_count": MIN_COUNT,
            "min_contexts": MIN_CONTEXTS,
            "purity": 1.0,
        },
        "inputs": {
            "product_decisions_csv": str(PRODUCT_DECISIONS_CSV),
            "resolved_keys": int(len(resolved)),
            "label_store_active": int(len(label_store.active())),
        },
        "n_phrases": int(len(lex)),
        "build_seconds": round(time.time() - t0, 2),
    }
    LEXICON_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return lex


def load_lexicon(path=LEXICON_PATH) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["phrase", "label", "n", "purity", "n_contexts"])
    return pd.read_parquet(p)


@click.command("build-lexicon")
def build_lexicon_command():
    """Regenerate the global phrase lexicon from label_store + product_decisions."""
    lex = build_lexicon()
    click.echo(f"lexicon: {len(lex)} phrases -> {LEXICON_PATH}")
    probes = ["lip gloss", "apple", "fanta", "coca cola"]
    hits = dict(zip(lex["phrase"], lex["label"]))
    for pr in probes:
        click.echo(f"  probe {pr!r}: {hits.get(pr, '<not indexed>')}")
