"""Repair the JSON-LD malformations storefronts actually ship.

``iter_jsonld_nodes`` used to call ``json.loads`` once and drop the whole
script on any exception, so a single stray byte cost the entire page. Measured
across 8,744 archived miss pages, 2,324 carry an ``application/ld+json``
script that produced no row, and **30% of those are malformed rather than
empty** -- the JSON is repairable and the Product node is sitting inside it.

Every cause here was found in that corpus, and the stages are ordered cheapest
first so a well-formed page pays only one ``raw_decode``.
"""

from __future__ import annotations

import html as _html
import json
import re
from typing import Any, Iterator

# Python's json accepts the non-standard NaN/Infinity literals, so they slip
# through the strict stage as floats and reach the price column as `nan`.
# Turn them into null at the decoder instead.
_DECODER = json.JSONDecoder(parse_constant=lambda _x: None)

# Shift_JIS lead bytes pair with a 0x5C trail byte on many kana/kanji, so a
# page mis-decoded as latin-1 leaves a bare backslash mid-string. JSON reads
# it as the start of an escape and dies (confirmed au_pay_market).
_BAD_ESCAPE = re.compile(r'\\(?![\\"/bfnrtu])')
_BAD_UNICODE = re.compile(r"\\u(?![0-9a-fA-F]{4})")
# JS values that are not JSON. `"sku":undefined` is confirmed on
# yahoo_shopping_tw, where a template wrote the variable straight through.
_JS_LITERAL = re.compile(r"(:\s*)(undefined|NaN|-?Infinity)\s*(?=[,}\]])")
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_CDATA = re.compile(r"^\s*(?://)?\s*<!\[CDATA\[(.*?)\]\]>\s*$", re.DOTALL)
_HTML_COMMENT = re.compile(r"^\s*<!--(.*?)-->\s*$", re.DOTALL)
# Raw control characters are illegal inside a JSON string; descriptions with
# hand-written newlines and tabs are common (confirmed fairprice).
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
# `"description":"<a href="/x">"` -- unescaped quotes from an HTML attribute
# inlined into a JSON string value (confirmed au_pay_market).
_HTML_ATTR_QUOTE = re.compile(r'(=)"([^"<>]*)"(?=[\s/>])')

_STAGE_NAMES = ("strict", "ctrl", "jslit", "escape", "htmlattr", "entity")


def _stages(raw: str) -> Iterator[str]:
    """Progressively more aggressive rewrites, cheapest first."""
    s = raw
    m = _CDATA.match(s) or _HTML_COMMENT.match(s)
    if m:
        s = m.group(1)
    yield s
    s1 = _CTRL.sub(" ", s)
    yield s1
    s2 = _JS_LITERAL.sub(r"\1null", s1)
    s2 = _TRAILING_COMMA.sub(r"\1", s2)
    yield s2
    s3 = _BAD_UNICODE.sub(r"\\\\u", s2)
    s3 = _BAD_ESCAPE.sub(r"\\\\", s3)
    yield s3
    yield _HTML_ATTR_QUOTE.sub(r'\1\\"\2\\"', s3)
    if "&quot;" in raw or "&amp;" in raw:
        u = _html.unescape(raw)
        yield _BAD_ESCAPE.sub(r"\\\\", _JS_LITERAL.sub(r"\1null", _CTRL.sub(" ", u)))


def _decode_all(s: str) -> tuple[list[Any], bool]:
    """``(values, consumed_everything)`` for every top-level JSON value.

    A single script tag legitimately holding two concatenated objects makes
    ``json.loads`` raise "Extra data" and lose both (confirmed fairprice, 61
    pages); ``raw_decode`` in a loop keeps them.
    """
    out: list[Any] = []
    i, n = 0, len(s)
    while i < n:
        while i < n and s[i] in " \t\r\n,;":
            i += 1
        if i >= n:
            break
        try:
            val, end = _DECODER.raw_decode(s, i)
        except ValueError:
            return out, False
        out.append(val)
        i = end
    return out, True


def parse_ld(raw: str) -> tuple[list[Any], str]:
    """``(values, how)`` -- the most conservative stage that works.

    A stage that parses only a prefix is not enough to stop on: the tail it
    dropped may hold the Product node. Keep looking for a stage that consumes
    the whole blob, and fall back to the longest partial result only if none
    does.
    """
    best: list[Any] = []
    best_how = "unparseable"
    for how, s in zip(_STAGE_NAMES, _stages(raw)):
        vals, full = _decode_all(s)
        if vals and full:
            return vals, how
        if len(vals) > len(best):
            best, best_how = vals, how + "_partial"
    return best, best_how
