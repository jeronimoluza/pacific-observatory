"""Per-source extractors for archived pages no standardised tier can read.

Some large storefronts never emitted JSON-LD, microdata or a product OpenGraph
tag in the era Common Crawl holds them, so every portable surface in
``archived.py`` abstains and the capture is banked as a miss. Three sources
account for 3.2M of the 18M misses on their own -- rakuten, ebay_uk and
tata_1mg -- and each writes its price into a stable, hand-readable class that
outlived a decade of redesigns.

This tier runs last, after every generic surface has already failed, so it can
only ever add rows to pages that yield none today.

The house rule for each extractor is to abstain rather than guess. These pages
are dense with figures that are not the product's price -- loyalty points,
postage, a manufacturer's list price, a rail of substitute drugs, a
foreign-currency conversion -- and banking one of those writes a wrong number
into a historical series where nothing downstream can detect it.
"""

from __future__ import annotations

import re
from typing import Any

from urllib.parse import urljoin

import lxml.etree
import lxml.html

from .archived import _dedupe_product_rows, normalize_price, price_row as _row
from .archived_livingcost import extract as _livingcost
from .archived_lohaco import extract as _lohaco
from .archived_eu import extract_edeka24 as _edeka24_de, extract_elvi as _elvi_lv
from .archived_momo import extract as _momo_tw
from .archived_frisco import extract as _frisco_pl
from .archived_chemist import extract as _chemist_warehouse
from .archived_classifieds import (
    extract_olx_pk as _olx_pk,
    extract_pakwheels_pk as _pakwheels_pk,
    extract_somon_tj as _somon_tj,
)
from .archived_ekupi import extract as _ekupi_hr
from .archived_emart import extract as _emart_kr
from .archived_gmarket import extract as _gmarket
from .archived_yahoo_tw import extract as _yahoo_shopping_tw
from .archived_sklavenitis import extract as _sklavenitis_gr
from .archived_taw9eel import extract as _taw9eel_kw
from .archived_happycenter import extract as _happycenter_tr
from .archived_mojsupermarket import extract as _mojsupermarket_me
from .archived_supermax import extract as _supermax_pr
from .archived_voli import extract as _voli_me
from .archived_sas_am import extract as _sas_am
from .archived_spar_zw import extract as _spar_zw

_YEN = re.compile("^[\\d,]+\\s*円$")
_GBP = re.compile("£\\s*[\\d,]+(?:\\.\\d+)?")
_EBAY_PRICE_BOXES = frozenset({"vi-price", "vi-price-np"})
_RUPEE = re.compile("^\\s*₹\\s*[\\d,]+(?:\\.\\d+)?\\s*$")
_TITLE_TAIL = re.compile("\\s*:\\s*")

# One per 1mg page template, oldest first: the class stem that era hangs its
# unconditional price on, and whether a further figure under the same stem is
# expected. Only the plan-option era repeats the stem, for a care-plan member
# price that always follows the open one in document order.
_ONEMG_PRICE_STEMS = (
    ("DrugPriceBox__price__", False),
    ("DrugPriceBox__bestprice-slashed-price__", False),
    ("PriceBoxPlanOption__offer-price__", True),
)

_YEN_FIGURE = re.compile("([\\d,]{2,})\\s*円")
# Figures a Japanese storefront prints that are never the product's price, and
# the thresholds they are quoted against.
_YEN_NOISE = re.compile("送料|手数料|以上|未満|以下|ポイント|還元|クーポン|金額")
# A name quoting money is describing postage or a bundle, not naming a product.
_YEN_BADNAME = re.compile("円|￥|¥|金額|削除|検索|絞り込")
_YAHOO_MIN_NAME = 6
_YAHOO_MIN_GRID = 2

_RAKUTEN_BANNER = "【楽天市場】"
_FULLWIDTH_COLON = "："


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _og_title(doc: Any) -> str | None:
    for el in doc.iter("meta"):
        if (el.get("property") or "").strip().lower() == "og:title":
            v = el.get("content")
            if v and v.strip():
                return " ".join(v.split())
    return None


def _title(doc: Any) -> str | None:
    el = doc.find(".//title")
    if el is None:
        return None
    return _text(el) or None


def _rakuten(doc: Any, url: str) -> dict | None:
    """``span.price2`` is the shop's price and ``.item_name`` names the item.

    ``price2`` is reused for the loyalty-points line, so only a bare yen amount
    qualifies. The manufacturer's list price lives in ``double_price`` and is
    deliberately not read -- it is what the item costs elsewhere, not here.

    The name cannot come from the title. Some shop templates title the page
    with its category path rather than the product, and those are exactly the
    URLs holding several variants of one item, so a title-derived name pairs a
    breadcrumb with whichever variant's price happened to come first. Counting
    ``item_name`` separates the two cases: one means a single item, several
    means a variant page this tier has no way to pair up and abstains on. The
    ``lossleader_item_name`` rail is a different class and is never counted --
    it advertises other shops' products, not this page's.

    A capture with no ``item_name`` at all is an older template whose title is
    the product, so that falls back to the title with the site's own banner and
    shop suffix removed.
    """
    price = None
    for el in doc.iter("span"):
        if "price2" in _classes(el) and _YEN.match(_text(el)):
            price = normalize_price(_text(el), "JPY")
            break

    names = {_text(el) for el in doc.iter() if "item_name" in _classes(el)}
    names.discard("")
    if len(names) > 1:
        return None
    if names:
        return _row(names.pop(), price, url, "JPY")

    name = (_og_title(doc) or _title(doc) or "").replace(_RAKUTEN_BANNER, "", 1)
    if _FULLWIDTH_COLON in name:
        name = name.rsplit(_FULLWIDTH_COLON, 1)[0]
    return _row(name.strip() or None, price, url, "JPY")


def _tata_1mg(doc: Any, url: str) -> dict | None:
    """The price a buyer pays with no conditions attached, in any page era.

    Three templates appear in the corpus and none of them names that figure
    the same way. The oldest prints the selling price outright, already net of
    any discount. The next prints the MRP beside a "Best Price" valid only
    above a basket threshold, so the MRP is what an unconditional buyer pays.
    The newest prints an open offer price, a struck-through MRP and a
    care-plan member price, so the open offer price is the one to take.

    Reading whichever figure is largest, or always the MRP, would put a
    discounted price in one year and a sticker price in the next and show a
    price change the shelf never had. Consistency here is the whole point of
    the tier.

    The near-miss figures are the danger: ``price-tablet`` is the same money
    divided by the pack size, and the ``SubstituteItem__`` rail prices a
    different drug entirely. Matching a class *stem* keeps those out while
    tolerating the trailing CSS-module build hash, which differs between eras.
    A page carrying an unexpected second figure under a stem is not one this
    tier can read, and a banned drug carries no figure at all.

    Titles read ``<drug>: View Uses, Side Effects, Price ...``, with the space
    before the colon present in older captures and absent in newer ones.
    """
    price = None
    for stem, repeats in _ONEMG_PRICE_STEMS:
        figures = [
            _text(el) for el in doc.iter()
            if isinstance(el.tag, str)
            and any(c.startswith(stem) for c in _classes(el))
            and _RUPEE.match(_text(el))
        ]
        if not figures:
            continue
        if len(set(figures)) > 1 and not repeats:
            return None
        price = normalize_price(figures[0], "INR")
        break
    name = _title(doc) or _og_title(doc) or ""
    name = _TITLE_TAIL.split(name, 1)[0]
    return _row(name.strip() or None, price, url, "INR")


def _ebay_uk(doc: Any, url: str) -> dict | None:
    """The item price, which lives in eBay's price box and nowhere else.

    The page is full of sterling figures that would pass any price-shaped
    test and are not this item's price: postage in ``#fshippingCost``, the
    seller's other-items rail in ``span.price``, and up to seventeen
    recommendations in ``.mfe-price``. Reading a known box rather than
    searching for a price is what keeps those out.

    Two box classes appear across the corpus -- ``vi-price`` on the older
    template and ``vi-price-np`` on the newer -- and a page may carry an empty
    one beside a filled one, so the figures are pooled and one distinct value
    is required. That also handles the foreign-currency case for free: a US or
    Australian listing shown on ebay.co.uk leaves the box with no sterling
    figure at all, and a was/now pair leaves two, and neither is banked.

    Many captures carry no title; a price with no name is not an observation.
    """
    figures = set()
    for el in doc.iter("div"):
        if not _EBAY_PRICE_BOXES & set(_classes(el)):
            continue
        figures.update(_GBP.findall(_text(el)))
    price = normalize_price(figures.pop(), "GBP") if len(figures) == 1 else None
    name = _og_title(doc) or _title(doc) or ""
    if name.endswith("| eBay"):
        name = name[: -len("| eBay")]
    return _row(name.strip() or None, price, url, "GBP")


def _yahoo_shopping(doc: Any, url: str) -> list[dict]:
    """Every product a Yahoo storefront's grid prices, read by structure alone.

    This source is not one shop but 21,814 of them: Yahoo hands each merchant a
    free-form storefront, so unlike rakuten or ebay there is no class to key on.
    Measured over 96 captures, the most common class wrapping a real price
    appears on six of them. What the pages do share is the shape of a grid --
    a repeated block holding one product link and one yen figure -- and that is
    what this reads.

    Most captures are category, search or guide pages rather than a single
    product, so this returns a list rather than one row, and returns an empty
    one for the majority that price nothing.

    Reading by structure means the figures that are not prices have to be
    excluded by hand, and on these pages there are many: a shipping fee, a
    free-postage threshold, a points-back line, a price-filter widget. Two
    guards do most of that work. A figure is skipped when its own text or an
    ancestor's names one of those things, and a candidate is skipped when the
    name itself quotes money -- the shape that otherwise banks a carbon number
    plate at the 240 yen postage printed inside its title.

    The last two guards are the ones worth stating plainly, because neither is
    a vocabulary rule and so both survive markup this tier has never seen.

    A name carrying several different prices on one page does not identify a
    product. That is what a shipping rate table looks like -- one "こちら >>>"
    link against five rates -- and dropping those cost nothing else on the
    design set, where it removed ten rows and every one was noise.

    Each row carries the product's own link rather than the capture's URL, so a
    product keeps one identity across every category page that lists it, which
    is what a price series is keyed on.

    A grid lists more than one product, so a capture yielding a single pair is
    not a grid and is banked as nothing. Every wrong row this tier produced on
    the held-out set was a lone pair: a 650 yen postage quote named "送料に
    ついての詳細はこちら" and a 540 yen fee named "ご注文ガイド". Requiring two
    cost one real row across 170 captures and removed both.

    Widening the noise vocabulary to the name instead was measured and rejected:
    it removed one of those two and six real products along with them, because a
    Japanese product title advertising 送料無料 is naming free shipping, not
    charging for it.
    """
    pairs = []
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        text = " ".join((el.text or "").split())
        if not text:
            continue
        found = _YEN_FIGURE.search(text)
        if not found:
            continue

        context, parent, up = text, el.getparent(), 0
        while parent is not None and up < 3:
            context += " " + " ".join((parent.text or "").split())
            parent, up = parent.getparent(), up + 1
        if _YEN_NOISE.search(context):
            continue

        name = href = None
        parent, up = el.getparent(), 0
        while parent is not None and up < 5:
            linked = [(" ".join((a.text_content() or "").split()), a.get("href"))
                      for a in parent.iter("a")]
            linked = [(t, h) for t, h in linked if t]
            if len(linked) == 1:
                name, href = linked[0]
                break
            parent, up = parent.getparent(), up + 1
        if name is None or len(name) < _YAHOO_MIN_NAME or _YEN_BADNAME.search(name):
            continue
        target = urljoin(url, href) if href else url
        if not target.startswith("http"):
            target = url
        pairs.append((name, found.group(0), target))

    prices_per_name: dict[str, set] = {}
    for name, price, _ in pairs:
        prices_per_name.setdefault(name, set()).add(price)

    rows = []
    for name, price, target in dict.fromkeys(pairs):
        if len(prices_per_name[name]) > 1:
            continue
        row = _row(name, normalize_price(price, "JPY"), target, "JPY")
        if row:
            rows.append(row)
    return rows if len(rows) >= _YAHOO_MIN_GRID else []


def _ckgreaves_vc(doc: Any, url: str) -> list[dict]:
    """Every card a C.K. Greaves department grid prices, read from attributes.

    The theme is WordPress "supershop" and it publishes nothing portable: no
    JSON-LD, no OpenGraph product tag, no Next.js payload, and an ``itemscope``
    carrying no ``itemtype``, which the microdata tier correctly refuses because
    there is no schema.org type for the properties to bind to. Every generic
    surface abstains, so these pages bank as misses today.

    The price is read from ``data-price`` rather than the rendered text, and
    that is the point of this extractor. The visible figure is split across
    three elements for typography -- ``<span>$</span><strong>61</strong>
    <em>20</em>`` -- so flattening the card to text gives "$6120", and any
    figure-shaped fallback banks 6120 for a 61.20 product. A hundredfold error
    is not a parse failure: nothing downstream can detect it, and it would sit
    in the series looking like a real observation.

    ``data-price`` of "0" means price on request, not free; the shared row
    builder drops it along with anything else non-positive.

    The name is anchored on ``itemprop="name"`` because every card also holds a
    "Login for a Better Experience" heading inside a modal, and taking the first
    ``h4`` reads that instead of the product.

    Two templates carry these cards -- ``product-grid-item`` on a department
    grid, ``single-product-post`` on a product page -- so the test is the
    ``data-price`` attribute itself rather than either class. That is also the
    safer test: a product page embeds five grid cards in a related-products rail
    and exactly one ``data-price``, and the site's dated blog posts render a
    twelve-item mini-cart rail whose widgets use the same split markup and carry
    no ``data-price`` at all. Reading the figure instead of the attribute would
    bank a hundredfold error against an obituary.

    Each row carries the card's own ``data-url`` rather than the capture's, so a
    product keeps one identity across every department page that lists it, which
    is what the price series is keyed on.
    """
    rows = []
    for card in doc.iter("article"):
        price = card.get("data-price")
        if price is None:
            continue
        name = ""
        for el in card.iter():
            if el.get("itemprop") == "name":
                name = _text(el)
                break
        href = card.get("data-url") or ""
        row = _row(name or None, normalize_price(price, "XCD"),
                   urljoin(url, href) if href else url, "XCD")
        if row:
            rows.append(row)
    return rows


_EXTRACTORS = {
    "rakuten": _rakuten,
    "lohaco": _lohaco,
    "gmarket": _gmarket,
    "tata_1mg": _tata_1mg,
    "chemist_warehouse": _chemist_warehouse,
    "ekupi_hr": _ekupi_hr,
    "ebay_uk": _ebay_uk,
    "edeka24_de": _edeka24_de,
    "elvi_lv": _elvi_lv,
    "momo_tw": _momo_tw,
    "frisco_pl": _frisco_pl,
    "yahoo_shopping": _yahoo_shopping,
    "yahoo_shopping_tw": _yahoo_shopping_tw,
    "emart_kr": _emart_kr,
    "olx_pk": _olx_pk,
    "somon_tj": _somon_tj,
    "pakwheels_pk": _pakwheels_pk,
    "livingcost": _livingcost,
    "sklavenitis_gr": _sklavenitis_gr,
    "taw9eel_kw": _taw9eel_kw,
    "happycenter_tr": _happycenter_tr,
    "mojsupermarket_me": _mojsupermarket_me,
    "supermax_pr": _supermax_pr,
    "voli_me": _voli_me,
    "sas_am": _sas_am,
    "spar_zw": _spar_zw,
    "ckgreaves_vc": _ckgreaves_vc,
}


def rows_from_source(html_text: str, url: str, source: str | None) -> list[dict]:
    """The price row this source's own markup carries, if one is written here."""
    fn = _EXTRACTORS.get(source or "")
    if fn is None or not html_text:
        return []
    try:
        doc = lxml.html.fromstring(html_text)
    except (ValueError, SyntaxError, lxml.etree.ParserError):
        return []
    got = fn(doc, url)
    if isinstance(got, list):
        # A grid extractor has already deduped on its own terms and every row
        # is a different product. The shared helper is built for a product
        # page: once several names are present it keeps only rows whose url is
        # the page's, which would collapse a whole category listing to one row.
        return got
    return _dedupe_product_rows([got], url) if got else []
