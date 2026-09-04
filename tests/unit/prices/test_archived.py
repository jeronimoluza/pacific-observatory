"""Unit tests for the spider-independent JSON-LD/OpenGraph extractors."""

from __future__ import annotations

import pytest

from prices.price_scraping.archived import (
    normalize_price,
    row_from_meta,
    rows_from_jsonld,
)


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


@pytest.mark.unit
def test_normalize_price_drops_currency_symbol_with_embedded_dot():
    """Peru's Sol symbol is ``S/.`` and Bolivia's is ``Bs.`` -- both carry
    their own trailing period. Rendered microdata text puts the symbol
    before the number (confirmed on archived plazavea_pe and fidalga_bo
    pages: ``<p itemprop="price">S/. 18.50</p>``), so the old strip kept
    that period, butted it against the real decimal point, and the "two
    dots means thousands separators" rule collapsed "18.50" into "1850" --
    a 100x inflation that reached global_prices_trusted_observations for
    Peru rice in 2017 and Bolivia rice in 2022-2025."""
    assert normalize_price("S/. 18.50") == "18.5"
    assert normalize_price("Bs. 13.50") == "13.5"
    assert normalize_price("S/.320.00") == "320.0"


@pytest.mark.unit
def test_normalize_price_still_resolves_eu_us_thousands_ambiguity():
    """The fix must not disturb the existing dot/comma disambiguation."""
    assert normalize_price("1.234,56") == "1234.56"
    assert normalize_price("1,234.56") == "1234.56"
    assert normalize_price("1.234.567") == "1234567.0"
    assert normalize_price("-45.00") == "-45.0"


@pytest.mark.unit
def test_normalize_price_keeps_a_bare_leading_decimal():
    """A price with no integer part and no symbol -- ".99" -- has only one
    dot before the digit-anchored trim runs, so it must not be swept up by
    the currency-symbol fix: its only prefix character is the dot itself,
    not a letter/symbol, so the trim must leave it alone."""
    assert normalize_price(".99") == "0.99"
