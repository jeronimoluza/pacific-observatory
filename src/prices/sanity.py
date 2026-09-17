"""Is this shard filed under the country it is about?

Every row in the corpus is stamped with a country taken from the directory its
source config sits in, never from the row. That is fine while a source covers
one country, and silently wrong when it does not: the samoa `livingcost` shard
holds 975,737 rows stamped `samoa`, of which the overwhelming majority are
product URLs for other countries entirely. Nothing in the pipeline noticed,
because nothing in the pipeline ever compares the stamp against the row.

The URL is the one field that carries a country independently of the stamp, so
it is the only available second opinion. Reading a country out of a URL is not
reliable in general -- `turkey`, `china` and `chile` are groceries, and half the
vanity ccTLDs (`.tv`, `.io`, `.me`, `.ws`, `.to`) have nothing to do with their
country -- so this does not try to read one row's URL in isolation.

What it does instead is look for a **country slot**: a position in the URL that
names a country on most of the shard's rows. `livingcost.org/cost/<country>/<city>`
has one at path segment 1; a grocery site that happens to sell turkey does not,
because one product in a thousand does not make a slot. Only once a slot exists
is any row judged, and then only against the shard's own stamp. Absence of
evidence is never a mismatch.

This makes the check self-validating on real data: `livingcost` in japan and in
vanuatu has the same slot at the same position and reports zero foreign rows,
while `livingcost` in samoa reports 91%. Same source, same parser, same slot --
so the signal is the filing, not the site.

Records loudly and changes nothing. A false positive that quarantined a good
shard would be worse than today's silence.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import click

from prices import lineage
from prices.partition import Shard, select

_PRICES_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"

# A slot must name a country on at least this share of the shard's rows before
# any row is judged against it. Set at a half because the two shapes are not
# close together: a real slot sits at ~1.0 (it is how the site builds its URLs)
# and an incidental product word sits near zero. Nothing measured lands between.
COUNTRY_SLOT_MIN_FRAC = 0.5

# Enough rows to establish whether a slot exists; the foreign count that follows
# is exact over the whole shard. A slot that needs more than this many rows to
# show itself is below the threshold anyway.
_SLOT_SAMPLE_ROWS = 20_000

_BATCH_ROWS = 65_536


def _country_vocabulary() -> dict[str, str]:
    """Every country the pipeline knows, keyed by the spellings a URL uses.

    The registry is the config tree itself -- the same directory level the
    country stamp is read from -- so the detector cannot disagree with the
    pipeline about what a country is, and no external mapping has to be trusted.
    """
    vocab: dict[str, str] = {}
    for path in _PRICES_CONFIGS_DIR.glob("*/*/*"):
        if not path.is_dir() or path.name.startswith("_"):
            continue
        name = path.name
        for spelling in (name, name.replace("_", "-"), name.replace("_", "")):
            vocab[spelling] = name
    return vocab


_VOCAB = _country_vocabulary()


def _slots(url: str) -> list[tuple[str, str]]:
    """(slot, country) for every position in this URL that names a country.

    Host labels and the first four path segments, whole-token only: a segment is
    `japan`, never `japanese-knives`. Partial matching is what turns `chile`
    into a false positive.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return []
    found = []
    labels = parsed.netloc.lower().partition(":")[0].split(".")
    segments = [s for s in parsed.path.lower().strip("/").split("/") if s][:4]
    for prefix, tokens in (("host", labels), ("seg", segments)):
        for index, token in enumerate(tokens):
            country = _VOCAB.get(token)
            if country is not None:
                found.append((f"{prefix}{index}", country))
    return found


@dataclass(frozen=True)
class ShardVerdict:
    """What the URLs of one shard say about the country it is filed under."""

    key: str
    country: str
    n_rows: int
    n_examined: int  # equals n_rows once a slot is found; the sample cap if not
    slot: Optional[str]
    slot_frac: float
    n_foreign: int
    top_foreign: tuple[tuple[str, int], ...]

    @property
    def flagged(self) -> bool:
        return self.n_foreign > 0

    @property
    def foreign_frac(self) -> float:
        return self.n_foreign / self.n_examined if self.n_examined else 0.0


def _open(path: Path):
    """The shard's row count, and its product URLs one batch at a time.

    Streamed rather than loaded: the largest shard is 35.7M rows, and its URL
    column alone does not need to be resident to be counted. The row count comes
    from the footer, so it is the shard's true height even when only a sample of
    its URLs is read.
    """
    import pyarrow.parquet as pq

    handle = pq.ParquetFile(path)

    def batches():
        for batch in handle.iter_batches(
            batch_size=_BATCH_ROWS, columns=["product_url"]
        ):
            yield [u for u in batch.column("product_url").to_pylist() if u]

    return handle.metadata.num_rows, batches()


def judge_shard(shard: Shard) -> Optional[ShardVerdict]:
    """Compare this shard's URLs against the country it is filed under.

    Returns None when the shard cannot be judged at all -- not a parquet, no
    URL column, empty. A shard with no country slot returns a verdict with
    `slot=None` and zero foreign rows, which is the ordinary healthy answer and
    the one almost every shard gives.
    """
    if shard.path.suffix != ".parquet":
        return None
    try:
        n_rows, batches = _open(shard.path)
    except Exception:
        return None

    seen = 0
    slot_hits: collections.Counter[str] = collections.Counter()
    held: list[list[str]] = []
    for batch in batches:
        held.append(batch)
        for url in batch:
            for slot, _ in _slots(url):
                slot_hits[slot] += 1
        seen += len(batch)
        if seen >= _SLOT_SAMPLE_ROWS:
            break
    if seen == 0:
        return None

    slot, hits = slot_hits.most_common(1)[0] if slot_hits else (None, 0)
    if slot is None or hits / seen < COUNTRY_SLOT_MIN_FRAC:
        return ShardVerdict(
            shard.key, shard.country, n_rows, seen, None, hits / seen, 0, ()
        )

    # A slot exists, so every row is now worth judging. The sample is replayed
    # rather than re-read.
    n_examined = 0
    foreign: collections.Counter[str] = collections.Counter()
    slotted = 0
    for batch in _chain(held, batches):
        n_examined += len(batch)
        for url in batch:
            for found_slot, country in _slots(url):
                if found_slot != slot:
                    continue
                slotted += 1
                if country != shard.country:
                    foreign[country] += 1

    verdict = ShardVerdict(
        key=shard.key,
        country=shard.country,
        n_rows=n_rows,
        n_examined=n_examined,
        slot=slot,
        slot_frac=slotted / n_examined if n_examined else 0.0,
        n_foreign=sum(foreign.values()),
        top_foreign=tuple(foreign.most_common(5)),
    )
    if verdict.flagged:
        lineage.record(
            stage="sanity",
            site="sanity.py:judge_shard",
            reason="country-vs-url",
            n_in=verdict.n_examined,
            scope=verdict.key,
            slot=verdict.slot,
            n_foreign=verdict.n_foreign,
            top_foreign=list(verdict.top_foreign),
        )
    return verdict


def _chain(held, rest):
    yield from held
    yield from rest


def judge(selectors=None) -> list[ShardVerdict]:
    """Every judgeable shard matching `selectors`, worst first."""
    verdicts = [v for v in (judge_shard(s) for s in select(selectors)) if v]
    return sorted(verdicts, key=lambda v: (-v.foreign_frac, -v.n_foreign, v.key))


@click.command("sanity")
@click.option(
    "--only",
    multiple=True,
    metavar="SELECTOR",
    help=(
        "Judge only part of the corpus. A selector is a glob over "
        "region/subregion/country/source. Repeatable."
    ),
)
def sanity_command(only: tuple[str, ...]) -> None:
    """Flag shards whose URLs name a country other than the one they are filed under."""
    verdicts = judge(list(only) or None)
    flagged = [v for v in verdicts if v.flagged]
    with_slot = [v for v in verdicts if v.slot]
    click.echo(
        f"{len(verdicts)} shards judged, {len(with_slot)} carry a country slot, "
        f"{len(flagged)} mismatch"
    )
    for v in flagged:
        top = ", ".join(f"{c} {n:,}" for c, n in v.top_foreign)
        click.echo(
            f"  {v.key:55s} {v.slot:5s} {v.n_foreign:>9,}/{v.n_examined:<9,} "
            f"({v.foreign_frac:5.1%})  {top}"
        )
    # Non-zero exit is what lets a sweep notice without anyone reading the log.
    if flagged:
        raise SystemExit(1)
