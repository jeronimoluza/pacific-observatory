"""Compatibility shim: the FX implementation now lives in :mod:`prices.fx`.

``prices`` used to reach into ``fuel.fx`` for the date-keyed attach, which
this module's own docstring described as a workaround -- it wanted a
prices-owned cache so the two pipelines would not contend. Following that to
its conclusion, the whole fetcher/cache/attach stack is now prices-owned and
tracked at ``src/prices/fx/``; nothing here imports ``fuel`` any more.

This module stays so ``from prices.build.fx import attach_fx_and_usd`` keeps
working. The public signature and behaviour of :func:`attach_fx_and_usd` are
unchanged.
"""

from __future__ import annotations

from prices.fx.aliases import (
    CURRENCY_TO_ISO,
    normalize_currency_safe as _normalize_currency_safe,
)
from prices.fx.attach import (
    _fill_from_latest_rate,
    attach_fx_and_usd,
    build_fx_table,
)
from prices.fx.cache import load_cache as _load_cache
from prices.fx.paths import PRICES_FX_CACHE, REPO_ROOT

__all__ = [
    "CURRENCY_TO_ISO",
    "PRICES_FX_CACHE",
    "REPO_ROOT",
    "attach_fx_and_usd",
    "build_fx_table",
]
