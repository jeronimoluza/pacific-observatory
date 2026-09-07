"""Vietnamobile Vietnam SIM and data-product storefront."""

from __future__ import annotations

from ._prestashop_base import PrestashopBaseSpider


class VietnamobileVnSpider(PrestashopBaseSpider):
    name = "vietnamobile_vn"
    allowed_domains = ["shop.vietnamobile.com.vn"]
    HOME_URL = "https://shop.vietnamobile.com.vn/vn/2-trang-chu"
    currency = "VND"
    language = "vi"
    custom_settings = {
        **PrestashopBaseSpider.custom_settings,
        "COOKIES_ENABLED": False,
    }
