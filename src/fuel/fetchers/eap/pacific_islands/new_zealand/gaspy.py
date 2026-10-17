"""New Zealand Gaspy daily national average prices.

Thin wrapper over the legacy fetcher ported unchanged into
``fuel.fetchers._shared.eap.new_zealand``.
"""

from fuel.fetchers._shared.eap.new_zealand import fetch_nz_gaspy_stats_daily

__all__ = ["fetch_nz_gaspy_stats_daily"]
