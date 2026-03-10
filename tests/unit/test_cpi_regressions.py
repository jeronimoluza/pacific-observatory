from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from cpi.coicopping.gemini_client import parse_gemini_response
from cpi.price_scraping.price_scraping.wayback_scraper import WaybackScraper


def test_parse_gemini_response_keeps_valid_final_row_without_trailing_quote():
    response_text = "\n".join(
        [
            "product_w_cat,coicop_code,confidence",
            '"rice; staples",01.1.2.0.0,0.91',
            '"soap; household",05.6.1.0.0,0.72',
        ]
    )

    results = parse_gemini_response(response_text)

    assert results == [
        {
            "product_w_cat": "rice; staples",
            "coicop_code": "01.1.2.0.0",
            "confidence": 0.91,
        },
        {
            "product_w_cat": "soap; household",
            "coicop_code": "05.6.1.0.0",
            "confidence": 0.72,
        },
    ]


def test_parse_gemini_response_drops_incomplete_trailing_row():
    response_text = "\n".join(
        [
            "product_w_cat,coicop_code,confidence",
            '"rice; staples",01.1.2.0.0,0.91',
            '"soap; household',
        ]
    )

    results = parse_gemini_response(response_text)

    assert results == [
        {
            "product_w_cat": "rice; staples",
            "coicop_code": "01.1.2.0.0",
            "confidence": 0.91,
        }
    ]


def test_fetch_wayback_snapshots_encodes_product_url_query_params(monkeypatch):
    captured = {}

    def fake_run(command, capture_output, text, timeout):
        captured["cdx_url"] = command[-1]

        class Result:
            returncode = 0
            stderr = ""
            stdout = (
                "[["
                '"urlkey","timestamp","original","mimetype","statuscode","digest","length"],'
                '["key","20240102030405",'
                '"https://example.com/product?sku=1&variant=blue",'
                '"text/html","200","digest","123"]]'
            )

        return Result()

    monkeypatch.setattr(
        "cpi.price_scraping.price_scraping.wayback_scraper.subprocess.run",
        fake_run,
    )

    scraper = WaybackScraper("rbpatel", Path("/tmp"), "2024-01-31")
    product_url = "https://example.com/product?sku=1&variant=blue#details"

    snapshots = scraper._fetch_wayback_snapshots(product_url)

    parsed_query = parse_qs(urlsplit(captured["cdx_url"]).query)
    assert parsed_query["url"] == [product_url]
    assert parsed_query["to"] == ["20240131"]
    assert snapshots == [
        "https://web.archive.org/web/20240102030405/https://example.com/product?sku=1&variant=blue"
    ]
