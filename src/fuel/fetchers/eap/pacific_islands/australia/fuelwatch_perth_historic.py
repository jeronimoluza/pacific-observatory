"""Australia FuelWatch WA (Perth) historic monthly CSV (manual backfill).

Thin wrapper over the legacy fetcher ported unchanged into
``fuel.fetchers._shared.eap.australia_fuelwatch``.
"""

from fuel.fetchers._shared.eap.australia_fuelwatch import fetch_au_fuelwatch_historic_csv

__all__ = ["fetch_au_fuelwatch_historic_csv"]
