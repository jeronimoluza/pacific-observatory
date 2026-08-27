"""Repair the JSON-LD malformations storefronts actually ship.

Every cause found in the miss corpus, in the order they need applying. The
shipped `iter_jsonld_nodes` calls `json.loads` once and drops the whole
script on any exception, so a single stray byte costs the entire page.
"""
import html as _html
import json
import re

# Python's json accepts the non-standard NaN/Infinity literals, so they slip
# through the strict stage as floats and reach the price column as `nan`.
# Turn them into null at the decoder instead.
_DECODER = json.JSONDecoder(parse_constant=lambda _x: None)

# Shift_JIS lead bytes pair with a 0x5C trail byte on many kana/kanji, so a
# page mis-decoded as latin-1 leaves a bare backslash mid-string. JSON reads
# it as the start of an escape and dies (confirmed au_pay_market).
_BAD_ESCAPE = re.compile(r'\\(?![\\"/bfnrtu])')
_BAD_UNICODE = re.compile(r'\\u(?![0-9a-fA-F]{4})')
# JS values that are not JSON. `"sku":undefined` is confirmed on
# yahoo_shopping_tw, where a template wrote the variable straight through.
_JS_LITERAL = re.compile(r"(:\s*)(undefined|NaN|-?Infinity)\s*(?=[,}\]])")
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_CDATA = re.compile(r"^\s*(?://)?\s*<!\[CDATA\[(.*?)\]\]>\s*$", re.DOTALL)
_HTML_COMMENT = re.compile(r"^\s*<!--(.*?)-->\s*$", re.DOTALL)
# Raw control characters are illegal inside a JSON string; descriptions with
# hand-written newlines and tabs are common (confirmed fairprice).
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
# `"description":"<a href="/x">"` - unescaped quotes from an HTML attribute
# inlined into a JSON string value (confirmed au_pay_market).
_HTML_ATTR_QUOTE = re.compile(r'(=)"([^"<>]*)"(?=[\s/>])')


def _stages(raw):
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
        yield _BAD_ESCAPE.sub(r"\\\\", _JS_LITERAL.sub(r"\1null",
                                                       _CTRL.sub(" ", u)))


def _decode_all(s):
    """(values, consumed_everything) for every top-level JSON value.

    A single script tag legitimately holding two concatenated objects makes
    `json.loads` raise "Extra data" and lose both (confirmed fairprice, 61
    pages); `raw_decode` in a loop keeps them.
    """
    out, i, n = [], 0, len(s)
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


def parse_ld(raw):
    """(list_of_values, how) - the most conservative stage that works.

    A stage that parses only a prefix is not enough to stop on: the tail it
    dropped may hold the Product node. Keep looking for a stage that consumes
    the whole blob, and fall back to the longest partial result only if none
    does.
    """
    names = ("strict", "ctrl", "jslit", "escape", "htmlattr", "entity")
    best, best_how = [], "unparseable"
    for how, s in zip(names, _stages(raw)):
        vals, full = _decode_all(s)
        if vals and full:
            return vals, how
        if len(vals) > len(best):
            best, best_how = vals, how + "_partial"
    return best, best_how
