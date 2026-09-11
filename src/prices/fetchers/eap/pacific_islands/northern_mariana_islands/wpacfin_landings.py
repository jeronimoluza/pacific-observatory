"""Canonical wrapper for the WPacFIN commercial-landings price series."""

from prices.fetchers._shared.eap.wpacfin_landings import fetch_mp_wpacfin_landings

fetch_mp_wpacfin_landings.__module__ = __name__
__all__ = ["fetch_mp_wpacfin_landings"]
