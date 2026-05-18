"""Canonical wrapper for World Bank RTEP in Gambia, The."""

from fuel.fetchers._shared.ssa.wb_rtep import fetch_wb_rtep_gm

fetch_wb_rtep_gm.__module__ = __name__

__all__ = ["fetch_wb_rtep_gm"]
