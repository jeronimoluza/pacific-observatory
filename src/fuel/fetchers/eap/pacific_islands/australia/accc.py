"""Australia ACCC quarterly retail averages, 5 largest cities.

Thin wrapper over the legacy fetcher ported unchanged into
``fuel.fetchers._shared.eap.australia_aip_accc``.
"""

from fuel.fetchers._shared.eap.australia_aip_accc import fetch_accc

__all__ = ["fetch_accc"]
