"""Australia NSW FuelCheck station-level price history (Data.NSW CKAN).

Thin wrapper over the legacy fetcher ported unchanged into
``fuel.fetchers._shared.eap.australia_nsw``.
"""

from fuel.fetchers._shared.eap.australia_nsw import fetch_au_nsw_fuelcheck_history

__all__ = ["fetch_au_nsw_fuelcheck_history"]
