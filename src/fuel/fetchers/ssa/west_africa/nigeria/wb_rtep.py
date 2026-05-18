"""Canonical wrapper for World Bank RTEP in Nigeria."""

from fuel.fetchers._shared.ssa.wb_rtep import fetch_wb_rtep_ng

fetch_wb_rtep_ng.__module__ = __name__

__all__ = ["fetch_wb_rtep_ng"]
