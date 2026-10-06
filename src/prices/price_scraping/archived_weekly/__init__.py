"""Per-source parsers written by the weekly CC parser stage (``cc_parsers.sh``).

One module per source, named for the config stem, exposing
``extract(html: str, url: str) -> list[dict]`` (rows built with
``prices.price_scraping.archived.price_row``). The ladder calls them only after
every other tier found nothing, so a parser here can add rows to a missed page
but never change a page that already parses -- that is the regression guarantee
the unattended stage relies on.

Abstain rather than guess: a figure that is not the product\x27s own current price
(points, postage, list price, a substitute\x27s price) is a wrong row nothing
downstream can detect.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

EXTRACTORS: Dict[str, Callable[[str, str], List[dict]]] = {}
for _info in pkgutil.iter_modules(__path__):
    if not _info.name.startswith("_"):
        EXTRACTORS[_info.name] = importlib.import_module(f"{__name__}.{_info.name}").extract


def rows_from_weekly(html_text: str, url: str, source: str | None) -> List[dict]:
    fn = EXTRACTORS.get(source or "")
    if fn is None or not html_text:
        return []
    try:
        return [r for r in fn(html_text, url) or [] if r]
    except Exception:
        logger.debug("weekly extractor failed for %s %s", source, url, exc_info=True)
        return []
