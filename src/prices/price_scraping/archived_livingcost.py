"""Reference item prices from archived livingcost.org city pages.

READ THIS BEFORE USING THESE ROWS. Unlike every other source in this package,
these are not observed retail prices. livingcost.org publishes crowd-sourced
and modelled estimates for a basket of about fifty items per city, already
converted to US dollars. They are a benchmark to compare a measured series
against, not a measurement, and nothing downstream can tell the difference
from the row alone -- the source key is the only thing that separates them.

Only single-city pages are read ("Cost of Living in Blankenberge | Belgium").
The site also publishes city-versus-city comparison pages, whose table prints
two figures per row under two column headers; attributing a column to the
wrong city would file New York's cappuccino under Mashhad, and the ambiguity
buys nothing that a single-city capture does not already give. Comparison
pages abstain. Measured over the cached corpus, single-city captures are all
of the 2020 sample but only about a quarter of 2025's, so this reads a
shrinking share of the source over time.

Row selection is by shape rather than by CSS class. An item row is "label, one
price" and has two cells; the cost-of-living summary (label, one person,
family) and the nearest-cities widget (distance, city, monthly budget) both
have three, so a two-cell rule excludes them without naming them. The class
that first looked semantic here, `table-str`, turned out to be a truncation of
Bootstrap's `table-striped` -- styling, not meaning, and it would not survive
a redesign.
"""

from __future__ import annotations

import re
from typing import Any

from .archived import normalize_price, price_row

_VS = re.compile(r"\bvs\.?\b", re.IGNORECASE)
_MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")

# Every genuine item label on this site is prefixed with an emoji -- "🥛 Milk,
# 1 L or 1 qt", "💇 Haircut, simple" -- on all 30 single-city captures spanning
# 2020 to 2025. Two captures also carry a US-states table whose rows are
# "Alabama | $1,234": two cells and a dollar figure, exactly the item shape,
# but a state's monthly budget rather than anything purchasable. The emoji is
# what separates them, so it is required rather than merely stripped.
_EMOJI_PREFIXED = re.compile(r"^[^\x00-\x7F]")
_HAS_WORD = re.compile(r"[A-Za-z]{3}")

# Two rows sit inside the item tables and are not prices at any scale.
_NOT_A_PRICE = re.compile(
    r"monthly salary|salary after tax|gdp per capita", re.IGNORECASE)


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _cells(row: Any) -> list[str]:
    return [_text(c) for c in row
            if isinstance(c.tag, str) and c.tag in ("th", "td")]


def _clean_name(label: str) -> str:
    """The item label without its leading emoji.

    Walked character by character rather than stripped against a character
    set, because these prefixes are multi-codepoint: "👩\u200d⚕️" is an emoji,
    a zero-width joiner, another emoji and a variation selector, and several
    labels carry a trailing variation selector of their own.
    """
    i = 0
    while i < len(label) and not label[i].isascii():
        i += 1
    return label[i:].strip(" .,:-")


def extract(doc: Any, url: str) -> list[dict]:
    """Every basket item this city page prices, or nothing.

    Returns a list because one capture carries the whole basket, which is the
    same shape the other grid extractors in this package use: each row is a
    different item at the same URL, and the caller must not collapse them.
    """
    heading = doc.find(".//h1")
    title = _text(heading) if heading is not None else ""
    if not title or _VS.search(title):
        return []

    rows = []
    seen = set()
    for row in doc.iter("tr"):
        cells = _cells(row)
        if len(cells) != 2:
            continue
        label, value = cells
        if not _EMOJI_PREFIXED.match(label) or not _HAS_WORD.search(label):
            continue
        if _NOT_A_PRICE.search(label):
            continue
        found = _MONEY.search(value)
        if not found:
            continue
        name = _clean_name(label)
        if not name or name in seen:
            continue
        seen.add(name)
        built = price_row(name, normalize_price(found.group(1), "USD"),
                          url, "USD")
        if built:
            rows.append(built)
    return rows
