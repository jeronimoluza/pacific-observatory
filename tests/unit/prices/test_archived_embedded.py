"""Unit tests for the Next.js flight-payload generic extractor."""

from __future__ import annotations

import json

import pytest

from prices.price_scraping.archived_embedded import (
    extract_flight_candidates,
    rows_from_next_flight,
)


def _flight_html(*chunks: str) -> str:
    """Wrap raw flight-payload text fragments as `self.__next_f.push` tags,
    the way a Next.js App Router page actually renders them."""
    parts = []
    for chunk in chunks:
        parts.append(f"<script>self.__next_f.push([1,{json.dumps(chunk)}])</script>")
    return "<html><body>" + "".join(parts) + "</body></html>"


@pytest.mark.unit
def test_rows_from_next_flight_reads_flat_schema():
    """Shape confirmed on aeonfoodstyle.netsuper.aeon.com: flat `name` /
    `includingTaxPrice` fields, id-first key order."""
    html = _flight_html(
        '0:{"id":4901810983957,"name":"Milk 1000ml","price":"200","includingTaxPrice":"213"}'
    )
    rows = rows_from_next_flight(
        html, "https://shop.test/articles/1?productId=4901810983957"
    )
    assert len(rows) == 1
    assert rows[0]["product_name"] == "Milk 1000ml"
    assert rows[0]["price"] == "213.0"
    assert rows[0]["product_id"] == "4901810983957"


@pytest.mark.unit
def test_rows_from_next_flight_reads_nested_locale_and_price_group():
    """Shape confirmed on onmart.mn: `title` is a locale dict, price lives
    under a nested `prices` object, and `sku` is overloaded with a free-text
    variant descriptor rather than an identifier -- `barcode` must win."""
    chunk = (
        '0:{"id":"uuid-1","productId":"pid-1","sku":" 75\\u043c\\u043b | note",'
        '"barcode":"123456789","title":{"en":"Toothbrush"},'
        '"prices":{"originalPrice":"12350.00","price":"12350.00"}}'
    )
    html = _flight_html(chunk)
    rows = rows_from_next_flight(html, "https://onmart.test/product/uuid-1")
    assert len(rows) == 1
    assert rows[0]["product_name"] == "Toothbrush"
    assert rows[0]["price"] == "12350.0"
    assert rows[0]["product_id"] == "123456789"


@pytest.mark.unit
def test_rows_from_next_flight_narrows_to_the_url_matching_product():
    """A product-detail page's flight payload can also embed a "related
    items" rail (confirmed on onmart.mn: ~30 unrelated objects). Only the
    row whose id appears in the URL itself should be kept -- attributing
    every rail item to this URL would corrupt its historical series the
    next time the rail rotates to different products."""
    chunks = (
        '0:{"id":"target-id","name":"Target Product","price":"5.00"}',
        '1:{"id":"other-id","name":"Unrelated Rail Item","price":"9.00"}',
    )
    html = _flight_html(*chunks)
    rows = rows_from_next_flight(html, "https://shop.test/product/target-id")
    assert len(rows) == 1
    assert rows[0]["product_name"] == "Target Product"


@pytest.mark.unit
def test_rows_from_next_flight_returns_all_candidates_when_no_url_match():
    """No id in the payload correlates with the URL at all -- e.g. an
    article-listing page (confirmed on aeonfoodstyle.netsuper.aeon.com) --
    so every extracted candidate is returned rather than guessing which one
    is "the" product."""
    chunks = (
        '0:{"id":"a","name":"Product A","price":"1.00"}',
        '1:{"id":"b","name":"Product B","price":"2.00"}',
    )
    html = _flight_html(*chunks)
    rows = rows_from_next_flight(html, "https://shop.test/articles/999")
    assert {r["product_name"] for r in rows} == {"Product A", "Product B"}


@pytest.mark.unit
def test_rows_from_next_flight_ignores_objects_without_both_name_and_price():
    """Negative control confirmed on setec.mk: the same flight protocol
    embeds i18n strings, nav/menu entries, and GraphQL layout components
    that happen to have an `id` key but no product data -- these must not
    be misread as products."""
    chunks = (
        '0:{"id":"clip0_3111_156","children":["$","rect",null,{"width":88}]}',
        '1:{"id":5,"title":{"en":"asd"},"name":{"en":"asd"},"variants":[],"option":"Radio"}',
    )
    html = _flight_html(*chunks)
    assert rows_from_next_flight(html, "https://shop.test/x") == []


@pytest.mark.unit
def test_rows_from_next_flight_returns_empty_for_no_flight_payload():
    assert (
        rows_from_next_flight(
            "<html><body>no scripts here</body></html>", "https://shop.test/x"
        )
        == []
    )


@pytest.mark.unit
def test_extract_flight_candidates_does_not_narrow_by_url():
    """The low-level building block a spider with listing-page semantics
    (aeon_foodstyle_jp) calls directly -- it must return every candidate,
    unfiltered, unlike the generic `rows_from_next_flight` wrapper."""
    chunks = (
        '0:{"id":"target-id","name":"Target Product","price":"5.00"}',
        '1:{"id":"other-id","name":"Unrelated Item","price":"9.00"}',
    )
    html = _flight_html(*chunks)
    candidates = extract_flight_candidates(html)
    assert len(candidates) == 2
    names = {row["product_name"] for row, _ids in candidates}
    assert names == {"Target Product", "Unrelated Item"}
