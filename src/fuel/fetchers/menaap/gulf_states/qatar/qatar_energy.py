"""Canonical wrapper for Qatar Energy in Qatar."""

from fuel.fetchers.menaap.qatar_energy import (
    _parse_page1_ocr,
    _parse_page2_text,
    fetch_qa_qatarenergy,
)

_parse_page1_ocr.__module__ = __name__
_parse_page2_text.__module__ = __name__
fetch_qa_qatarenergy.__module__ = __name__

__all__ = ["_parse_page1_ocr", "_parse_page2_text", "fetch_qa_qatarenergy"]
