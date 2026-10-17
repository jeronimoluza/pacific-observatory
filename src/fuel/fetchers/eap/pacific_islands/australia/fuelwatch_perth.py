"""Australia FuelWatch WA (Perth) daily retail prices via RSS.

Thin wrapper over the legacy fetcher ported unchanged into
``fuel.fetchers._shared.eap.australia_fuelwatch``.
"""

from fuel.fetchers._shared.eap.australia_fuelwatch import fetch_au_fuelwatch_perth

__all__ = ["fetch_au_fuelwatch_perth"]
