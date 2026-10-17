"""Split a product priced in more than one currency into one product per currency.

`input_hash` for a row with a URL is (source, name, url): currency is not in it.
A listing priced in two currencies (lun_ua: 90,000 USD and 3,848,000 UAH) was
therefore one product, `prepare` stored the median across both scales, and the
modal currency was stamped on it (1,969,000 "UAH").

Rule, applied to a written shard (one country, one source, whole history):

- Group rows by their stored `input_hash`; normalise currency with
  `prices.fx.normalize_currency_safe`, so an alias (KM and BAM) is ONE currency
  and never splits.
- A group with one normalised currency is untouched: its hash stays
  byte-identical, so its classify decision and history keep their key.
- A group with more than one: the PRIMARY currency keeps the hash -- the
  country's own currency (countries.yaml) when the group has it, else the one on
  the most rows, ties to the lexically smallest. Every other currency's rows get
  `input_hash({"input_hash": <old>, "currency": <normalised>})`. A row with no
  currency keeps the old hash.

URL-less rows already hash their raw currency, so their groups never hold two
codes and the rule leaves them alone. The pass is idempotent: once split, every
group holds one currency. It is a property of the whole group, so it runs on the
finished shard, not per batch; readers that take `input_hash` from the shard
(prepare, Stage B's dated rows, build) see it without change. The legacy
per-row recompute (`prepare._row_input_dict` when a frame has no hash,
`merge.py`, the CSV-monolith fallback in build) does not apply it.

A seller registered under two source names (`source_canonical`) sits in two
shards and is split per shard, not across both.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from core.config import load_countries
from prices.fx.aliases import normalize_currency_safe
from prices.enrich.versioning import input_hash

logger = logging.getLogger(__name__)
BATCH_ROWS = 200_000


@lru_cache(maxsize=1)
def _home_currency() -> dict[str, str]:
    return {
        slug: normalize_currency_safe(str(meta.get("currency") or ""))
        for slug, meta in load_countries().items()
    }


def _norm(code) -> str:
    if code is None:
        return ""
    return normalize_currency_safe(str(code).strip()) or ""


def split_shard(path: Path, country: str) -> int:
    """Re-key the non-primary currency rows of `path` in place. Returns the
    number of products split (0 leaves the file untouched)."""
    if not path.exists():
        return 0
    t = pq.read_table(path, columns=["input_hash", "currency"])
    pairs = t.group_by(["input_hash", "currency"]).aggregate([([], "count_all")])
    hashes = pairs["input_hash"].to_pylist()
    currencies = pairs["currency"].to_pylist()
    counts = pairs["count_all"].to_pylist()
    mapping = remap(hashes, currencies, counts, country)
    if not mapping:
        return 0
    n_split = len({h for h, _ in mapping})
    tmp = path.with_suffix(".currency_split.tmp")
    pf = pq.ParquetFile(path)
    schema = pf.schema_arrow
    idx = schema.get_field_index("input_hash")
    with pq.ParquetWriter(tmp, schema, compression="zstd") as writer:
        for batch in pf.iter_batches(batch_size=BATCH_ROWS):
            h = batch.column("input_hash").to_pylist()
            c = batch.column("currency").to_pylist()
            new = [mapping.get((a, b), a) for a, b in zip(h, c)]
            batch = batch.set_column(
                idx, schema.field(idx), pa.array(new, schema.field(idx).type)
            )
            writer.write_table(pa.Table.from_batches([batch], schema=schema))
    os.replace(tmp, path)
    logger.info(
        "[currency_hash] %s: %d products split, %d (hash, currency) pairs re-keyed",
        path.name,
        n_split,
        len(mapping),
    )
    return n_split


def remap(hashes: list, currencies: list, counts: list, country: str) -> dict:
    """`{(old_hash, raw_currency): new_hash}` for the rows that move, from the
    distinct (hash, raw currency) pairs and their row counts. Empty when no
    group holds more than one normalised currency."""
    tally: dict[str, dict[str, int]] = {}
    for h, c, k in zip(hashes, currencies, counts):
        n = _norm(c)
        if n:
            g = tally.setdefault(h, {})
            g[n] = g.get(n, 0) + k
    split = {h: g for h, g in tally.items() if len(g) > 1}
    if not split:
        return {}
    home = _home_currency().get(country, "")
    out = {}
    for h, c in zip(hashes, currencies):
        g = split.get(h)
        if g is None:
            continue
        primary = (
            home if home in g else min(g.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        )
        n = _norm(c)
        if n and n != primary:
            out[(h, c)] = input_hash({"input_hash": h, "currency": n})
    return out
