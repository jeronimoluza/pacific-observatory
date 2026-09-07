"""Unit tests for the spider-independent JSON-LD/OpenGraph extractors."""

from __future__ import annotations

import pytest

from prices.price_scraping.archived_microdata import rows_from_microdata
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


@pytest.mark.unit
def test_rows_from_jsonld_rescales_a_minor_unit_payload_against_the_rendered_price():
    """fidalga.com (Shopify, Bolivia) renders ``Bs10,40`` for a JSON-LD
    ``price`` of ``1040``: the theme emits Liquid's ``product.price``, which is
    cents. Banking the payload as written put 3,823 Bolivian rows into
    global_prices_observations at 100x, 20-44% of every year 2022-2025."""
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Product",
       "name":"Lavandina Mr Cloro de 1000 ml",
       "offers":{"@type":"Offer","price":"1040","priceCurrency":"BOB"}}
      </script>
      <span class="price-item">Bs10,40</span>
    </body></html>
    """
    rows = rows_from_jsonld(html, "https://www.fidalga.com/products/lavandina")
    assert len(rows) == 1
    assert rows[0]["price"] == "10.4"


@pytest.mark.unit
def test_rows_from_jsonld_leaves_the_payload_alone_when_the_page_agrees():
    """The guard must only fire when the page actually contradicts the blob."""
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Product","name":"Widget",
       "offers":{"@type":"Offer","price":"9.99","priceCurrency":"USD"}}
      </script>
      <span class="price">$9.99</span>
    </body></html>
    """
    rows = rows_from_jsonld(html, "https://example.test/p/widget")
    assert rows[0]["price"] == "9.99"


@pytest.mark.unit
def test_rows_from_jsonld_keeps_a_large_price_the_page_never_renders():
    """liverpool.com.mx ships ``minimumPromoPrice: '7939'`` and renders no
    price at all -- 7,939 pesos is the real figure, so with nothing to
    reconcile against the payload must stand exactly as written."""
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Product","name":"Sofa",
       "offers":{"@type":"Offer","price":"7939","priceCurrency":"MXN"}}
      </script>
    </body></html>
    """
    rows = rows_from_jsonld(html, "https://example.test/p/sofa")
    assert rows[0]["price"] == "7939.0"


@pytest.mark.unit
def test_rows_from_microdata_rescales_a_minor_unit_content_attribute():
    """The same failure reaches the microdata tier when the price rides a
    ``content=`` attribute in minor units while the shelf renders the real
    figure -- the plazavea_pe 2017 shape, in Peruvian soles."""
    html = """
    <html><body>
      <div itemscope itemtype="http://schema.org/Product">
        <span itemprop="name">Arroz COSTENO Extra graneadito Bolsa 5Kg</span>
        <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
          <meta itemprop="price" content="1890">
          <meta itemprop="priceCurrency" content="PEN">
        </div>
        <span class="shelf-price">S/. 18.90</span>
      </div>
    </body></html>
    """
    rows = rows_from_microdata(html, "https://www.plazavea.com.pe/arroz/p")
    assert len(rows) == 1
    assert rows[0]["price"] == "18.9"


@pytest.mark.unit
def test_rows_from_jsonld_reads_the_currency_off_a_price_specification():
    """tiki.vn states its money as a nested ``UnitPriceSpecification`` and
    puts no ``priceCurrency`` on the offer itself. ``_price_of`` already
    followed the specification for the amount, so the row kept the price and
    lost the currency -- 218,900 with no unit. Confirmed on the same shape at
    supermart.ng (NGN), delhaize.be and mega-image.ro (RON)."""
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Product",
       "name":"Bo Doi Goi Xa TSUBAKI 450ml",
       "offers":{"@type":"Offer","availability":"https://schema.org/InStock",
                 "priceSpecification":{"@type":"UnitPriceSpecification",
                                       "price":218900,"priceCurrency":"VND"}}}
      </script>
    </body></html>
    """
    rows = rows_from_jsonld(html, "https://tiki.vn/p7777255.html")
    assert len(rows) == 1
    assert rows[0]["price"] == "218900.0"
    assert rows[0]["currency"] == "VND"


@pytest.mark.unit
def test_rows_from_jsonld_reads_a_price_specification_written_as_a_list():
    """scotts.com.mt, pasarsegar.co.id, tripolimarket.com and ghl.com.bn all
    ship the specification as a one-element list rather than an object --
    the same shape ``_price_of`` already unwraps for the amount."""
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Product",
       "name":"ABC Saus Sambal 275 ml",
       "offers":{"@type":"Offer",
                 "priceSpecification":[{"@type":"UnitPriceSpecification",
                                        "price":"19000","priceCurrency":"IDR"}]}}
      </script>
    </body></html>
    """
    rows = rows_from_jsonld(html, "https://pasarsegar.co.id/product/abc/")
    assert rows[0]["currency"] == "IDR"


@pytest.mark.unit
def test_rows_from_jsonld_keeps_the_offers_own_currency_over_the_specification():
    """The specification is a fallback, not an override: an offer that states
    its own ``priceCurrency`` alongside the price the row actually took must
    keep it."""
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Product","name":"Widget",
       "offers":{"@type":"Offer","price":"9.99","priceCurrency":"USD",
                 "priceSpecification":{"@type":"UnitPriceSpecification",
                                       "price":"9.99","priceCurrency":"EUR"}}}
      </script>
    </body></html>
    """
    rows = rows_from_jsonld(html, "https://example.test/p/widget")
    assert rows[0]["currency"] == "USD"


@pytest.mark.unit
def test_row_from_meta_reads_the_itemprop_price_currency():
    """homecenter.com.co ships the schema.org pair as two ``<meta itemprop>``
    tags. The tier already read the amount half as the bare ``price`` key and
    ignored the currency half, which was not a missing label but a 1000x
    understatement: with no currency the three-digit tail of ``299.900`` reads
    as a decimal point, banking a 30-piece dinner set at 299.9 Colombian pesos
    instead of 299,900. COP is a de-facto-integer currency, so the currency is
    exactly what tells ``normalize_price`` the dot is a grouping mark."""
    html = """
    <html><head>
      <meta itemprop="name" content="Corona Vajilla Quadrato de 30 Piezas"/>
      <meta property="og:title" content="Corona Vajilla Quadrato de 30 Piezas"/>
      <meta itemprop="price" content="299.900"/>
      <meta itemprop="priceCurrency" content="COP"/>
    </head><body></body></html>
    """
    row = row_from_meta(html, "http://www.homecenter.com.co/product/189468/")
    assert row["currency"] == "COP"
    assert row["price"] == "299900.0"


@pytest.mark.unit
def test_row_from_meta_prefers_an_explicit_opengraph_currency():
    """``itemprop`` is tried last, so a storefront that declares an OpenGraph
    product currency still wins -- the ordering the tier shipped with."""
    html = """
    <html><head>
      <meta property="og:title" content="Widget"/>
      <meta property="product:price:amount" content="12.50"/>
      <meta property="product:price:currency" content="GBP"/>
      <meta itemprop="priceCurrency" content="USD"/>
    </head><body></body></html>
    """
    row = row_from_meta(html, "https://example.test/p/widget")
    assert row["currency"] == "GBP"
