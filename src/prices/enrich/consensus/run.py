"""Batch orchestration (W4.4 core): collect witness Votes over a corpus, apply
the gate per name, and return accepts (label_store-shaped) + conflicts.

Kept separate from the CLI so it can be exercised in tests with a tiny frame.
Every witness is optional/abstain-safe; ``use_knn`` / ``use_cascade`` let a fast
score-only pass skip the two heavy witnesses (index + spaCy).
"""

from __future__ import annotations

import pandas as pd

from prices.enrich.classifier.featurize import detect_script
from prices.enrich.consensus import gate, witnesses
from prices.enrich.consensus.witnesses import Vote
from prices.enrich.keys import norm_key

_CHEAP = ("memo", "lexicon", "model", "source")


def collect_votes(
    corpus: pd.DataFrame,
    name_col: str,
    country_col: str = "country",
    lang_col: str = "lang",
    use_knn: bool = True,
    use_cascade: bool = True,
) -> dict[str, list[Vote]]:
    names = corpus[name_col]
    votes: dict[str, list[Vote]] = {norm_key(n): [] for n in names}

    maps = {
        "memo": witnesses.w_memo(names),
        "lexicon": witnesses.w_lexicon(names),
        "model": witnesses.w_model(names),
        "source": witnesses.w_source(corpus, name_col),
    }
    if use_knn:
        maps["knn"] = witnesses.w_knn(corpus, name_col, country_col)
    if use_cascade:
        from prices.enrich.consensus._cascade import cascade_votes

        maps["cascade"] = cascade_votes(corpus, name_col, lang_col)

    for wmap in maps.values():
        for k, v in wmap.items():
            if k in votes:
                votes[k].append(v)
    return votes


def classify_frame(
    corpus: pd.DataFrame,
    name_col: str,
    country_col: str = "country",
    lang_col: str = "lang",
    use_knn: bool = True,
    use_cascade: bool = True,
    policy: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    policy = policy or gate.load_policy()
    votes = collect_votes(corpus, name_col, country_col, lang_col, use_knn, use_cascade)

    seen: dict[str, str] = {}
    for n in corpus[name_col]:
        seen.setdefault(norm_key(n), str(n))

    rows = [
        (k, gate.decide(votes.get(k, []), detect_script(name), policy))
        for k, name in seen.items()
    ]
    return gate.result_frame(rows)
