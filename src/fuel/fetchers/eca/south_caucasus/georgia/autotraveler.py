"""Canonical wrapper for autotraveler.ru in Georgia."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_ge

fetch_autotraveler_ge.__module__ = __name__

__all__ = ["fetch_autotraveler_ge"]
