"""Canonical wrapper for autotraveler.ru in Montenegro."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_me

fetch_autotraveler_me.__module__ = __name__

__all__ = ["fetch_autotraveler_me"]
