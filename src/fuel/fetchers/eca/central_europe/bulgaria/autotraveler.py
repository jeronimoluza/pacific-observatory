"""Canonical wrapper for autotraveler.ru in Bulgaria."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_bg

fetch_autotraveler_bg.__module__ = __name__

__all__ = ["fetch_autotraveler_bg"]
