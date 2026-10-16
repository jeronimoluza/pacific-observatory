"""Read-only status of ``text.ledger`` against ``text.corpus``, per source.

The ledger is ``<state_dir>/<region>.sqlite`` (table ``sources``: key, watermark, n_news,
n_urls, updated; table ``blocked``). The corpus is ``<corpus_root>/<region>/<key>/news.csv``.
For each source the ledger's ``n_news`` is compared with the distinct non-empty URLs of
news.csv and its ``watermark`` with the newest news.csv date (same rule as
``text.ledger.newest_date``). Differences are reported as drift, never corrected.
The sqlite file is opened read-only and is never written.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

STATE_DIR = Path.home() / "text_state"
CORPUS_ROOT = Path("/mnt/backup5tb/text-corpus")


def ledger_sources(region: str, state_dir: Path = STATE_DIR) -> dict[str, dict]:
    """Ledger rows by key (blobs not loaded); blocked keys carry ``blocked`` = error."""
    conn = sqlite3.connect(f"file:{state_dir / f'{region}.sqlite'}?mode=ro", uri=True)
    try:
        out = {
            k: {"watermark": w, "n_news": nn, "n_urls": nu, "ledger_updated": u, "blocked": None}
            for k, w, nn, nu, u in conn.execute(
                "SELECT key, watermark, n_news, n_urls, updated FROM sources ORDER BY key"
            )
        }
        for k, err in conn.execute("SELECT key, error FROM blocked ORDER BY key"):
            out.setdefault(k, {"watermark": None, "n_news": None, "n_urls": None,
                               "ledger_updated": None})["blocked"] = err
    finally:
        conn.close()
    return out


def corpus_news(news_csv: Path, today: date) -> dict:
    """Rows, distinct non-empty URLs and newest valid date (≤ today + 1) of one news.csv."""
    import pandas as pd

    urls: set[str] = set()
    rows = 0
    newest = None
    for chunk in pd.read_csv(news_csv, usecols=["url", "date"], dtype=str, chunksize=500_000):
        rows += len(chunk)
        urls.update(chunk["url"].dropna().astype(str))
        d = pd.to_datetime(chunk["date"].dropna().astype(str).str[:10], format="%Y-%m-%d",
                           errors="coerce")
        d = d[d <= pd.Timestamp(today + timedelta(days=1))].max()
        if not pd.isna(d) and (newest is None or d > newest):
            newest = d
    urls.discard("")
    return {"corpus_rows": rows, "corpus_urls": len(urls),
            "corpus_newest": newest.strftime("%Y-%m-%d") if newest is not None else None}


def corpus_keys(region: str, corpus_root: Path = CORPUS_ROOT) -> list[str]:
    region_dir = corpus_root / region
    return sorted(
        str(p.parent.relative_to(region_dir)) for p in region_dir.glob("*/*/*/news.csv")
        if not p.parent.name.startswith(".")
    )


def ledger_vs_corpus(region: str, state_dir: Path = STATE_DIR, corpus_root: Path = CORPUS_ROOT,
                     today: date | None = None, keys: list[str] | None = None) -> list[dict]:
    """One row per source in the ledger or the corpus, with ``drift`` (comma-joined, empty
    when they agree) and ``age_days`` = today − watermark (freshness)."""
    today = today or datetime.now(timezone.utc).date()
    ledger = ledger_sources(region, state_dir)
    on_disk = set(corpus_keys(region, corpus_root))
    rows = []
    for key in keys or sorted(set(ledger) | on_disk):
        led = ledger.get(key, {"watermark": None, "n_news": None, "n_urls": None,
                               "ledger_updated": None, "blocked": None})
        cor = (corpus_news(corpus_root / region / key / "news.csv", today) if key in on_disk
               else {"corpus_rows": None, "corpus_urls": None, "corpus_newest": None})
        drift = []
        if key not in ledger:
            drift.append("not_in_ledger")
        elif led["blocked"]:
            drift.append("blocked")
        if key not in on_disk:
            drift.append("not_in_corpus")
        if key in ledger and key in on_disk and not led["blocked"]:
            if led["n_news"] != cor["corpus_urls"]:
                drift.append("n_news")
            if led["watermark"] != cor["corpus_newest"]:
                drift.append("watermark")
        wm = led["watermark"]
        rows.append({
            "region": region, "key": key, **led, **cor, "drift": ",".join(drift),
            "age_days": (today - date.fromisoformat(wm)).days if wm else None,
        })
    return rows


def observe(node) -> list[dict]:
    """Graph contract (`text.ledger`): per owner (manifest ``owners``), one row per source of
    every ``<state>/<region>.sqlite``. Drift compares keys only (``not_in_corpus``,
    ``not_in_ledger`` among the corpus folders of countries the owner owns, ``blocked``);
    the n_news/watermark comparison reads every news.csv and stays in ``main``. Without
    the corpus mount, keys are not compared."""
    from graph.observe import row
    from graph.observers.text_owners import country_of_key, owner_of, root

    owners = node.owners or {"prod": {"state": str(STATE_DIR)}}
    out = []
    for owner, spec in owners.items():
        state = root(spec, "state")
        if not state or not state.is_dir():
            continue
        for sqlite in sorted(state.glob("*.sqlite")):
            region = sqlite.stem
            ledger = ledger_sources(region, state)
            have_corpus = (CORPUS_ROOT / region).is_dir()
            on_disk = {k for k in (corpus_keys(region, CORPUS_ROOT) if have_corpus else [])
                       if owner_of(owners, region, country_of_key(k)) == owner}
            for key in sorted(set(ledger) | on_disk):
                led = ledger.get(key)
                drift = []
                if led is None:
                    drift.append("not_in_ledger")
                elif led["blocked"]:
                    drift.append("blocked")
                if have_corpus and key not in on_disk and owner_of(owners, region, country_of_key(key)) == owner:
                    drift.append("not_in_corpus")
                out.append(row(node, f"{owner}/{region}/{key}", led is not None and not led["blocked"],
                               (led or {}).get("n_news"), (led or {}).get("ledger_updated"), drift=drift,
                               extra={"owner": owner, "watermark": (led or {}).get("watermark"),
                                      "owned": owner_of(owners, region, country_of_key(key)) == owner,
                                      "corpus_checked": have_corpus}))
    return out


def main(argv: list[str] | None = None) -> int:
    import pandas as pd

    ap = argparse.ArgumentParser(prog="python -m graph.observers.text_ledger")
    ap.add_argument("--region", required=True)
    ap.add_argument("--state-dir", type=Path, default=STATE_DIR)
    ap.add_argument("--corpus-root", type=Path, default=CORPUS_ROOT)
    ap.add_argument("--today", type=date.fromisoformat, help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--key", action="append", help="only these <sub>/<country>/<source> keys")
    a = ap.parse_args(argv)
    df = pd.DataFrame(ledger_vs_corpus(a.region, a.state_dir, a.corpus_root, a.today, a.key))
    cols = ["key", "n_news", "corpus_urls", "corpus_rows", "watermark", "corpus_newest",
            "age_days", "drift"]
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(df[cols].to_string(index=False))
    drifted = df[df["drift"] != ""]
    print(f"{a.region}: {len(df)} sources, {len(drifted)} with drift")
    return 1 if len(drifted) else 0


if __name__ == "__main__":
    sys.exit(main())
