import sys
from pathlib import Path

import pytest

_PRICES = Path(__file__).resolve().parents[2] / "src" / "prices"
if str(_PRICES) not in sys.path:
    sys.path.insert(0, str(_PRICES))

pytest.importorskip("scrapy")

from price_scraping.spiders._vtex_base import VtexBaseSpider  # noqa: E402


class _TestVtexSpider(VtexBaseSpider):
    name = "vtex_guard_test"
    HOST = "www.example.com"
    currency = "ARS"
    language = "es"


def _offer(price, qty):
    return {
        "sellerDefault": True,
        "commertialOffer": {"Price": price, "AvailableQuantity": qty},
    }


def _product(item_id, price, qty):
    return {
        "productName": "Azucar Impalpable Pergola Celeste Sin Tacc 250 Gr",
        "linkText": "azucar-impalpable-pergola-celeste",
        "categories": ["/Almacen/Para Preparar/Pasteleria/"],
        "items": [{"itemId": item_id, "sellers": [_offer(price, qty)]}],
    }


def _spider():
    spider = _TestVtexSpider()
    spider.seen_skus = set()
    return spider


def test_out_of_stock_offer_is_refused():
    """Cencosud AR banners (disco/jumbo/vea) serve their whole delisted SKU
    archive with AvailableQuantity=0 and a price frozen years ago -- 35.55 ARS
    for a bag of icing sugar. Those offers must not become price rows."""
    spider = _spider()
    assert list(spider._items(_product("260743", 35.55, 0), "Pasteleria")) == []


def test_in_stock_offer_is_emitted():
    spider = _spider()
    items = list(spider._items(_product("342878", 2350.0, 7), "Pasteleria"))
    assert len(items) == 1
    assert items[0]["price"] == "2350.0"
    assert items[0]["available"] is True


def test_unknown_quantity_is_kept():
    """Tenants that omit AvailableQuantity are unchanged -- absent is not zero."""
    spider = _spider()
    items = list(spider._items(_product("342879", 2350.0, None), "Pasteleria"))
    assert len(items) == 1


def _state(item_id, price, qty):
    return {
        "Product:azucar": {
            "productName": "Azucar Impalpable Pergola Celeste Sin Tacc 250 Gr",
            "linkText": "azucar-impalpable-pergola-celeste",
            "categories": ["/Almacen/Para Preparar/Pasteleria/"],
            "items": [{"itemId": item_id, "sellers": [_offer(price, qty)]}],
        }
    }


def test_archived_out_of_stock_offer_is_refused():
    rows = list(_TestVtexSpider._rows_from_state(_state("260743", 35.55, 0)))
    assert rows == []


def test_archived_in_stock_offer_is_emitted():
    rows = list(_TestVtexSpider._rows_from_state(_state("342878", 2350.0, 7)))
    assert len(rows) == 1
    assert rows[0]["price"] == "2350.0"
