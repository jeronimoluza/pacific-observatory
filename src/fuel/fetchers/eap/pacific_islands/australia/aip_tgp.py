"""Australia AIP terminal gate prices (wholesale), 7 capitals + national.

Thin wrapper over the legacy fetcher ported unchanged into
``fuel.fetchers._shared.eap.australia_aip_accc``.
"""

from fuel.fetchers._shared.eap.australia_aip_accc import fetch_au_aip_tgp

__all__ = ["fetch_au_aip_tgp"]
