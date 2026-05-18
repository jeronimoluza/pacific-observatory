"""Canonical wrapper for World Bank RTEP in Somalia."""

from fuel.fetchers._shared.ssa.wb_rtep import fetch_wb_rtep_so

fetch_wb_rtep_so.__module__ = __name__

__all__ = ["fetch_wb_rtep_so"]
