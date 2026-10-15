"""`prices.pages`: the 8 HTML pages of the observed week ({rtcal,trusted} ×
{dashboard,explorer} × {world,eap}), one row per page. Drift: a page missing or empty.
"""

from __future__ import annotations

from graph.observe import mtime, row
from graph.observers.prices_build import declared


def observe(node) -> list[dict]:
    out = []
    for page in declared(node, (".html",)):
        size = page.stat().st_size if page.exists() else 0
        drift = [] if size else ["missing" if not page.exists() else "empty"]
        out.append(row(node, f"{page.parent.name}/{page.name}", size > 0, None, mtime(page),
                       drift=drift, extra={"mb": round(size / 2**20, 1)}))
    return out
