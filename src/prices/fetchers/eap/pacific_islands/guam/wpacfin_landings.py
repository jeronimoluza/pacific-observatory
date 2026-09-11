"""Canonical wrapper for the WPacFIN commercial-landings price series."""

from prices.fetchers._shared.eap.wpacfin_landings import fetch_gu_wpacfin_landings

fetch_gu_wpacfin_landings.__module__ = __name__
__all__ = ["fetch_gu_wpacfin_landings"]
