"""Unit tests for the spider-independent JSON-LD/OpenGraph extractors."""

from __future__ import annotations

import pytest

from prices.price_scraping.archived import row_from_meta, rows_from_jsonld


@pytest.mark.unit
def test_rows_from_jsonld_reads_normal_script_body():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Widget",
     "sku":"W-1","offers":{"@type":"Offer","price":"9.99","priceCurrency":"USD"}}
    </script>
    </head></html>
    """
    rows = rows_from_jsonld(html, "https://example.test/product/widget")
    assert len(rows) == 1
    assert rows[0]["product_name"] == "Widget"
    assert rows[0]["price"] == "9.99"
    assert rows[0]["currency"] == "USD"


@pytest.mark.unit
def test_rows_from_jsonld_reads_html_attribute_children_with_embedded_gt():
    """Confirmed on billa.sk: a React/Nuxt theme renders JSON-LD into a
    ``children="..."`` attribute (HTML-entity-escaped) on an empty script
    tag instead of the tag body, and the category values inside legitimately
    contain a raw ``>`` (e.g. "LEAFLET > KW 37/2026 > Inside") that would
    truncate a naive ``[^>]*``-attribute regex before it ever reaches the
    JSON payload.
    """
    html = (
        '<script nonce="abc123" '
        'children="{&quot;@context&quot;:&quot;https://schema.org&quot;,'
        "&quot;@type&quot;:&quot;Product&quot;,"
        "&quot;category&quot;:[&quot;LEAFLET &gt; KW 37/2026 &gt; Inside&quot;],"
        "&quot;name&quot;:&quot;PAMPERS PREMIUM 60KS MIDI&quot;,"
        "&quot;offers&quot;:{&quot;@type&quot;:&quot;Offer&quot;,"
        "&quot;price&quot;:13.99,&quot;priceCurrency&quot;:&quot;EUR&quot;},"
        '&quot;sku&quot;:&quot;84-204092&quot;}" '
        'type="application/ld+json"></script>'
    )
    rows = rows_from_jsonld(
        html, "https://www.billa.sk/produkt/pampers-premium-60ks-midi-84204092"
    )
    assert len(rows) == 1
    assert rows[0]["product_name"] == "PAMPERS PREMIUM 60KS MIDI"
    assert rows[0]["price"] == "13.99"
    assert rows[0]["currency"] == "EUR"


@pytest.mark.unit
def test_rows_from_jsonld_ignores_non_ldjson_scripts_with_children_attr():
    html = (
        '<script nonce="abc123" children="{&quot;not&quot;:&quot;ldjson&quot;}" '
        'type="application/json"></script>'
    )
    assert rows_from_jsonld(html, "https://example.test/x") == []


@pytest.mark.unit
def test_row_from_meta_still_works_alongside_the_new_script_scanner():
    html = """
    <meta property="og:title" content="Widget">
    <meta property="product:price:amount" content="9.99">
    <meta property="product:price:currency" content="USD">
    """
    row = row_from_meta(html, "https://example.test/product/widget")
    assert row["product_name"] == "Widget"
    assert row["price"] == "9.99"
    assert row["currency"] == "USD"


@pytest.mark.unit
def test_country_code_is_not_accepted_as_a_currency():
    """`NIC` is Nicaragua's ISO 3166 code, not a currency — lacuracaonline_ni
    ships it where the store actually trades in NIO. A three-letter shape test
    accepts it; the price must survive with no currency rather than a wrong one."""
    html = (
        '<script type="application/ld+json">{"@type":"Product","name":"Arroz 1kg",'
        '"offers":{"@type":"Offer","price":"85.50","priceCurrency":"NIC"}}</script>'
    )
    rows = rows_from_jsonld(html, "https://example.test/p/arroz")
    assert rows[0]["price"] == "85.5"
    assert "currency" not in rows[0]

    ok = rows_from_jsonld(html.replace("NIC", "NIO"), "https://example.test/p/arroz")
    assert ok[0]["currency"] == "NIO"


@pytest.mark.unit
def test_iranian_toman_survives_the_iso_gate():
    """IRT is not ISO 4217 but eleven spiders carry a x10 multiplier for it."""
    html = (
        '<script type="application/ld+json">{"@type":"Product","name":"Chai",'
        '"offers":{"@type":"Offer","price":"50000","priceCurrency":"IRT"}}</script>'
    )
    assert rows_from_jsonld(html, "https://example.test/p/chai")[0]["currency"] == "IRT"
