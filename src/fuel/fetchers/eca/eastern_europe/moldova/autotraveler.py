"""Canonical wrapper for autotraveler.ru in Moldova."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_md

fetch_autotraveler_md.__module__ = __name__

__all__ = ["fetch_autotraveler_md"]
