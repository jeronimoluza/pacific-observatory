"""Unit tests for the Common Crawl columnar-index scanner."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from prices import cc_table, cc_triage
from prices.cc_table import Ledger, build_predicate, load_keyword_regex
from prices.cc_triage import _common_prefix


@pytest.mark.unit
def test_keyword_regex_is_slug_bounded(tmp_path: Path):
    terms = tmp_path / "terms.txt"
    terms.write_text("# a comment\nrice\ncoca-cola\nleche entera\nab\n")
    pattern = re.compile(load_keyword_regex(terms))

    assert pattern.search("/products/coca-cola-1-5l")
    assert pattern.search("/p/arroz/leche-entera-1l")
    assert pattern.search("/shop/rice.html")
    # `rice` inside `price` is the failure that swamps the candidate list.
    assert not pattern.search("/price-list/")
    # Terms under the length floor are dropped rather than matched everywhere.
    assert not pattern.search("/ab/")


@pytest.mark.unit
def test_build_predicate_requires_a_selector():
    with pytest.raises(ValueError):
        build_predicate()


@pytest.mark.unit
def test_build_predicate_escapes_quotes_in_domains():
    sql = build_predicate(domains=["o'reilly.com"])
    assert "'o''reilly.com'" in sql
    assert "fetch_status = 200" in sql


@pytest.mark.unit
def test_ledger_treats_an_errored_part_as_not_done(tmp_path: Path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.record("part-00000.parquet", "ok", rows=12)
    ledger.record("part-00001.parquet", "error", error="HTTP 503")
    assert ledger.done_parts() == {"part-00000.parquet": 12}

    # A retry that succeeds flips it, and a later failure flips it back, so a
    # throttled part is never mistaken for an empty one.
    ledger.record("part-00001.parquet", "ok", rows=3)
    assert ledger.done_parts()["part-00001.parquet"] == 3
    ledger.record("part-00000.parquet", "error", error="HTTP 503")
    assert "part-00000.parquet" not in ledger.done_parts()


@pytest.mark.unit
def test_common_prefix_stops_at_the_first_divergence():
    assert _common_prefix(["/producto/arroz", "/producto/leche"]) == "producto"
    assert _common_prefix(["/shop/p/a", "/shop/p/b"]) == "shop/p"
    assert _common_prefix(["/p/a", "/shop/b"]) is None
    assert _common_prefix([]) is None


@pytest.mark.unit
def test_html_from_record_strips_warc_and_http_envelopes():
    import gzip

    from prices.cc_triage import html_from_record

    body = "<html><body>hi</body></html>"
    record = (
        "WARC/1.0\r\nWARC-Type: response\r\n\r\n"
        "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + body
    ).encode()
    assert html_from_record(gzip.compress(record)) == body


@pytest.mark.unit
def test_html_from_record_returns_none_on_garbage():
    from prices.cc_triage import html_from_record

    assert html_from_record(b"not gzip at all") is None


@pytest.mark.unit
def test_probe_domain_reports_a_price_from_jsonld(monkeypatch, tmp_path: Path):
    import gzip

    from prices import cc_triage

    page = """
    <html><head><script type="application/ld+json">
    {"@type":"Product","name":"Arroz 1kg",
     "offers":{"@type":"Offer","price":"1250.00","priceCurrency":"ARS"}}
    </script></head><body></body></html>
    """
    record = gzip.compress(("WARC/1.0\r\n\r\nHTTP/1.1 200 OK\r\n\r\n" + page).encode())
    monkeypatch.setattr(cc_triage, "fetch_warc_record", lambda *a, **k: record)

    records = [
        {
            "url_host_name": "tienda.com.ar",
            "url_path": "/producto/arroz-1kg",
            "warc_filename": "f",
            "warc_record_offset": 0,
            "warc_record_length": 1,
        },
        {
            "url_host_name": "tienda.com.ar",
            "url_path": "/producto/leche-1l",
            "warc_filename": "f",
            "warc_record_offset": 0,
            "warc_record_length": 1,
        },
    ]
    out = cc_triage.probe_domain("tienda.com.ar", records)
    assert out["n_fetched"] == 2
    assert out["n_parsed"] == 2
    assert out["method"] == "jsonld"
    assert out["currency"] == "ARS"
    assert out["prefix_hint"] == "producto"


@pytest.mark.unit
def test_probe_domain_does_not_invent_a_row_when_nothing_parses(monkeypatch):
    import gzip

    from prices import cc_triage

    record = gzip.compress(
        b"WARC/1.0\r\n\r\nHTTP/1.1 200 OK\r\n\r\n<html><body>no markup</body></html>"
    )
    monkeypatch.setattr(cc_triage, "fetch_warc_record", lambda *a, **k: record)

    records = [
        {
            "url_host_name": "x.com",
            "url_path": "/a",
            "warc_filename": "f",
            "warc_record_offset": 0,
            "warc_record_length": 1,
        }
    ]
    out = cc_triage.probe_domain("x.com", records)
    assert out["n_fetched"] == 1
    assert out["n_parsed"] == 0
    assert out["method"] is None


@pytest.mark.unit
def test_scan_part_leaves_a_completed_output_alone_when_a_later_run_fails(
    monkeypatch, tmp_path: Path
):
    """A failing run must not delete a previous run's finished output."""
    from prices import cc_table

    out = tmp_path / "00001.parquet"
    out.write_bytes(b"already-complete")

    class _Result:
        returncode = 1
        stderr = "HTTP 503"
        stdout = ""

    monkeypatch.setattr(cc_table.subprocess, "run", lambda *a, **k: _Result())
    monkeypatch.setattr(cc_table.time, "sleep", lambda _s: None)
    monkeypatch.setattr(cc_table, "duckdb_binary", lambda: "duckdb")

    with pytest.raises(RuntimeError):
        cc_table.scan_part("http://x/part-00001-u.parquet", "TRUE", "discover", out)

    assert out.read_bytes() == b"already-complete"
    assert not list(tmp_path.glob("*.tmp"))


def _write_hits(tmp_path, with_warc: bool):
    """A stand-in discovery hits file, written by the real duckdb binary."""
    out = tmp_path / "00001.parquet"
    if with_warc:
        rows = (
            "('shop.example', 'www.shop.example', '/p/long-product-name-here', "
            "'a.warc.gz', 10, 20), "
            "('shop.example', 'www.shop.example', '/c/x', 'a.warc.gz', 30, 40), "
            "('other.example', 'other.example', '/p/thing', 'b.warc.gz', 50, 60)"
        )
        cols = (
            "url_host_registered_domain, url_host_name, url_path, warc_filename, "
            "warc_record_offset, warc_record_length"
        )
    else:
        rows = "('shop.example', '/p/one'), ('shop.example', '/p/two')"
        cols = "url_host_registered_domain, url_path"
    subprocess.run(
        [
            cc_table.duckdb_binary(),
            "-c",
            f"COPY (SELECT * FROM (VALUES {rows}) AS t({cols})) "
            f"TO '{out}' (FORMAT PARQUET);",
        ],
        check=True,
        capture_output=True,
    )
    return out


def test_collect_pointers_reads_warc_records_from_local_hits(tmp_path, monkeypatch):
    """Triage must get its pointers off disk, not by re-reading Common Crawl."""
    _write_hits(tmp_path, with_warc=True)
    monkeypatch.setattr(
        cc_triage, "hits_glob", lambda _index: str(tmp_path / "*.parquet")
    )

    got = cc_triage.collect_pointers("CC-MAIN-TEST", ["shop.example"], samples=1)

    assert list(got) == ["shop.example"]
    only = got["shop.example"][0]
    assert only["url_path"] == "/p/long-product-name-here"
    assert (only["warc_filename"], only["warc_record_offset"]) == ("a.warc.gz", 10)
    # probe_domain builds its URL from url_host_name, so a pointer missing it
    # is useless — www.shop.example and shop.example are not interchangeable.
    assert set(only) >= {"url_host_name", "url_path", "warc_record_length"}
    assert only["url_host_name"] == "www.shop.example"


def test_collect_pointers_names_the_rescan_when_hits_predate_the_pointers(
    tmp_path, monkeypatch
):
    """An old hits file must say what to rerun, not read as 'domain has no data'."""
    _write_hits(tmp_path, with_warc=False)
    monkeypatch.setattr(
        cc_triage, "hits_glob", lambda _index: str(tmp_path / "*.parquet")
    )

    with pytest.raises(RuntimeError, match="rerun `prices cc-table scan"):
        cc_triage.collect_pointers("CC-MAIN-TEST", ["shop.example"], samples=3)


def _triage_row(domain, live):
    return {
        "domain": domain,
        "n_parsed": 2,
        "n_sampled": 3,
        "method": "jsonld",
        "prefix_hint": "product",
        "country": "iran",
        "currency": "IRR",
        "live": live,
    }


@pytest.mark.parametrize("live", [True, False])
def test_manifest_drafts_load_through_the_real_config_model(
    tmp_path, monkeypatch, live
):
    """A draft that cannot be loaded is not a draft — it is a dead end.

    `channel` is required by PriceSourceConfig, so a writer that forgets it
    emits YAML nobody can promote into src/prices/configs/.
    """
    import json as _json

    import yaml

    from prices.config import PriceSourceConfig

    monkeypatch.setattr(cc_triage, "work_dir", lambda: tmp_path)
    (tmp_path / "CC-MAIN-TEST").mkdir()
    (tmp_path / "CC-MAIN-TEST" / "triage.jsonl").write_text(
        _json.dumps(_triage_row("kadolin.ir", live)) + "\n"
    )

    out_dir = cc_triage.write_manifest_drafts("CC-MAIN-TEST")
    body = yaml.safe_load((out_dir / "kadolin_ir.yaml").read_text())

    assert "channel" in body
    PriceSourceConfig(**body)

    # `prices collect` dispatches on exactly these two values; a live source
    # drafted as anything else is silently never collected.
    assert body["scaffolding"] == ("spider" if live else "archive_only")
    assert ("spider" in body) is live
