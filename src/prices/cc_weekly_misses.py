"""WARC access and miss-sampling helpers for ``prices cc-weekly``.

The Tuesday parser stage cannot read a WARC range itself, so ``--sample-misses``
saves miss pages as plain HTML (``<work>/<source>/NNN.html`` + ``index.jsonl``),
spread across eras because markup changes between them. ``--check`` runs the
current ladder over those files: a parser written against the first half of a
sample is judged on the second half.
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Dict, List

import click

from prices.cc_index import CC_DATA_BASE

_BAN_AFTER = 25
_BAN_PAUSE = 120
_MISS_REASONS = ("no_extract", "selectors_noprice")


class Ban(Exception):
    """Sustained 403s: stop rather than land a crawl with a hole in it."""


def fetch_raw(rec: dict, ban: Dict[str, int]) -> bytes:
    off, ln = int(rec["offset"]), int(rec["length"])
    req = urllib.request.Request(
        f"{CC_DATA_BASE}/{rec['filename']}", headers={"Range": f"bytes={off}-{off + ln - 1}"}
    )
    err: Exception = RuntimeError("no attempt")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            ban["n"] = 0
            return data
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                # data.commoncrawl.org 403s the whole address under sustained load
                # (W41: at 6-8 connections) and lifts within minutes once it eases,
                # so every worker backs off instead of failing the record. Counted
                # per record: a ban noticed only at the end looks like a thin crawl.
                ban["n"] += 1
                if ban["n"] >= _BAN_AFTER:
                    raise Ban(f"{_BAN_AFTER} consecutive 403s from {CC_DATA_BASE}") from exc
                err = exc
                time.sleep(_BAN_PAUSE)
                continue
            err = exc
        except Exception as exc:  # 503s and stalled transfers on cold objects
            err = exc
        time.sleep(5 * (attempt + 1))
    raise err


def split_warc(raw: bytes):
    """``(http_headers, body)`` or ``(None, reason)``; ARC-aware like ccfetch."""
    try:
        blob = gzip.decompress(raw)
    except Exception:
        return None, "gunzip_failed"
    if blob.startswith(b"WARC/"):
        i = blob.find(b"\r\n\r\n")
        if i < 0:
            return None, "no_warc_envelope"
    else:
        # ARC (2008-2012): one "url ip stamp mime len" line, then the response.
        i = blob.find(b"\n") - 3
    j = blob.find(b"\r\n\r\n", i + 4)
    if j < 0:
        return None, "no_http_headers"
    body = blob[j + 4:]
    if not body.strip():
        return None, "empty_body"
    return blob[i + 4:j], body


def sample_misses(stems: List[str], miss_dirs: List[Path], n: int, out: Path) -> None:
    from prices.price_scraping.archived_ladder import decode

    want = set(stems)
    misses: Dict[str, List[dict]] = {s: [] for s in stems}
    for d in miss_dirs:
        for f in sorted(d.glob("*.jsonl.gz")):
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    r = json.loads(line)
                    if r["source"] in want and r.get("reason") in _MISS_REASONS:
                        misses[r["source"]].append(r)
    ban = {"n": 0}
    for stem, recs in misses.items():
        recs.sort(key=lambda r: r["timestamp"])
        pick = recs[:: max(1, len(recs) // n)][:n]
        dest = out / stem
        dest.mkdir(parents=True, exist_ok=True)
        with (dest / "index.jsonl").open("w") as idx:
            for i, rec in enumerate(pick):
                try:
                    headers, body = split_warc(fetch_raw(rec, ban))
                except Ban:
                    raise
                except Exception:
                    continue
                if headers is None:
                    continue
                (dest / f"{i:03d}.html").write_text(decode(headers, body), encoding="utf-8")
                idx.write(json.dumps({"file": f"{i:03d}.html", "url": rec["url"],
                                      "timestamp": rec["timestamp"], "reason": rec["reason"]}) + "\n")
        click.echo(f"{stem}: {len(recs)} misses, sampled {len(pick)} -> {dest}")


def check_samples(root: Path) -> None:
    from prices.price_scraping.archived_ladder import parse_rows

    dirs = [root] if (root / "index.jsonl").exists() else sorted(
        p for p in root.iterdir() if (p / "index.jsonl").exists())
    for d in dirs:
        tiers, hit = Counter(), 0
        idx = [json.loads(line) for line in (d / "index.jsonl").open()]
        for rec in idx:
            html = (d / rec["file"]).read_text(encoding="utf-8")
            rows, tier = parse_rows(html, rec["url"], d.name)
            priced = [r for r in rows if r.get("price") not in (None, "")]
            tiers[tier] += 1
            hit += bool(priced)
            first = priced[0] if priced else {}
            click.echo(f"  {rec['file']} {rec['timestamp'][:8]} {tier:18} rows={len(priced):3} "
                       f"{str(first.get('price', '')):>10} {str(first.get('product_name', ''))[:50]}"
                       f"  {rec['url'][:70]}")
        click.echo(f"{d.name}: {hit}/{len(idx)} pages priced, tiers {dict(tiers)}")
