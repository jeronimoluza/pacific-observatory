"""Canonical wrapper for autotraveler.ru in Belarus."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_by

fetch_autotraveler_by.__module__ = __name__

__all__ = ["fetch_autotraveler_by"]
