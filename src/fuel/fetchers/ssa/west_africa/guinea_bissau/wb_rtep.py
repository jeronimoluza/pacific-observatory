"""Canonical wrapper for World Bank RTEP in Guinea-Bissau."""

from fuel.fetchers._shared.ssa.wb_rtep import fetch_wb_rtep_gw

fetch_wb_rtep_gw.__module__ = __name__

__all__ = ["fetch_wb_rtep_gw"]
