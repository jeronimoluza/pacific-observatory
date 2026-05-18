"""Canonical wrapper for World Bank RTEP in Liberia."""

from fuel.fetchers._shared.ssa.wb_rtep import fetch_wb_rtep_lr

fetch_wb_rtep_lr.__module__ = __name__

__all__ = ["fetch_wb_rtep_lr"]
