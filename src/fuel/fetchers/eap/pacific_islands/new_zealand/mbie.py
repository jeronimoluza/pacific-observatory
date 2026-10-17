"""New Zealand MBIE weekly fuel price monitoring.

Thin wrapper over the legacy fetcher ported unchanged into
``fuel.fetchers._shared.eap.new_zealand``.
"""

from fuel.fetchers._shared.eap.new_zealand import fetch_nz_mbie_weekly

__all__ = ["fetch_nz_mbie_weekly"]
