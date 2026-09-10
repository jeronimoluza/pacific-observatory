"""The one place a prices dashboard decides how much evidence a figure needs.

Almost every constant in `prices.explorer.sources` -- and three in
`prices.publish` -- is a minimum-evidence gate: a count, a share or a span that
decides whether a figure is drawn at all. Each was defensible on its own, and
together they suppressed a large part of what the corpus holds. On the corpus of
September 2026 they left 39 of the 208 countries that have a basket unranked and
never wrote 12.6% of the leaf x country grid.

Two things live here and nothing else does.

THE SWITCH. `PO_PRICES_UNFILTERED=1` in the environment takes EVERY gate to its
arithmetic floor -- a count to 1, a share to 0.0, a maximum gap to effectively
infinite -- and produces the DIAGNOSTIC build: no evidence gate anywhere,
figures that may rest on a single observation, a chained index that may link on
one pair. It is not a publication, and it says so on the page. Two things are
NOT switched off by it and both are choices rather than oversights, recorded so
the word "unfiltered" means something exact:

  COMPARABLE_UNITS still excludes `item`. That is a unit of measure, not a
  quantity of evidence -- `item` is the parse-failure bucket, and pooling it
  into `kg` is arithmetic across incommensurable quantities rather than a
  weaker measurement of the same thing.

  Residual "n.e.c." leaves are still barred from the matched basket, for the
  same reason: one country's "other bakery products" is not the other's, so a
  leaf-matched ratio over them measures composition, not price.

  The `qa_status == "trusted"` restriction IS lifted in `prices.publish` under
  this flag, which admits rows the QA layer rejected for a failed quantity
  parse, a failed FX lookup or an implausible unit value. That is what
  "unfiltered" has to mean, and it is also the single change most likely to put
  a nonsense number on the page.

THE STAMP. Every unfiltered output carries a banner saying what it is. It is
applied to the rendered FILE because the two dashboards keep separate templates
and neither belongs to this module.

The switch is read at import. Every consumer takes its constants by value at its
own import time, so the environment must be set before `prices.explorer` or
`prices.publish` is imported -- which is what `cli.py` does. There are
deliberately no conditionals anywhere else in the codebase.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

UNFILTERED = os.environ.get("PO_PRICES_UNFILTERED", "").strip().lower() not in (
    "",
    "0",
    "false",
    "no",
    "off",
)


def gate(normal, floor):
    """A publication threshold, or its arithmetic floor in the unfiltered build."""
    return floor if UNFILTERED else normal


def banner_html() -> str:
    """The stamp every unfiltered output carries. Empty string on a normal build."""
    if not UNFILTERED:
        return ""
    return (
        '<div id="unfiltered-banner" style="position:sticky;top:0;z-index:99999;'
        "background:#8a1c1c;color:#fff;font:600 13px/1.45 system-ui,-apple-system,"
        "'Segoe UI',sans-serif;padding:9px 16px;text-align:center;"
        'letter-spacing:.01em;box-shadow:0 1px 4px rgba(0,0,0,.35)">'
        "UNFILTERED DIAGNOSTIC BUILD &mdash; every evidence gate is disabled. "
        "A figure here may rest on a single observation, a price level on a "
        "basket of one item, a chained index on one linking pair. "
        "Nothing on this page is publishable, and nothing on it has been "
        "checked against the gates the real dashboards apply. "
        '<span style="font-weight:400;opacity:.85">'
        "Built with <code>--unfiltered</code>.</span></div>"
    )


def stamp_unfiltered(path) -> None:
    """Insert `banner_html` directly after <body> in a rendered dashboard.

    Done to the FILE rather than through either template, because the two
    dashboards keep their own and neither is this module's to edit. A single
    anchored insert; if the anchor is ever absent this raises rather than
    dropping the banner silently, because an unfiltered page without its banner
    is the exact failure this function exists to prevent.
    """
    if not UNFILTERED:
        return
    path = Path(path)
    html = path.read_text()
    m = re.search(r"<body[^>]*>", html, flags=re.I)
    if not m:
        raise RuntimeError(f"no <body> tag in {path}: refusing to ship an unstamped "
                           "unfiltered build")
    path.write_text(html[: m.end()] + banner_html() + html[m.end():])


def unfiltered_path(path: Path) -> Path:
    """`x.html` -> `x_unfiltered.html`, so a diagnostic can never land on a
    production output. Applied by the CLI to whatever path it was going to use,
    including an explicit --out, because the suffix is about what the file IS."""
    path = Path(path)
    if not UNFILTERED or path.stem.endswith("_unfiltered"):
        return path
    return path.with_name(path.stem + "_unfiltered" + path.suffix)
