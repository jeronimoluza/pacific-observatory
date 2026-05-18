"""Canonical wrapper for World Bank RTEP in South Sudan."""

from fuel.fetchers._shared.ssa.wb_rtep import fetch_wb_rtep_ss

fetch_wb_rtep_ss.__module__ = __name__

__all__ = ["fetch_wb_rtep_ss"]
