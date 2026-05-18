"""Canonical wrapper for autotraveler.ru in North Macedonia."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_mk

fetch_autotraveler_mk.__module__ = __name__

__all__ = ["fetch_autotraveler_mk"]
