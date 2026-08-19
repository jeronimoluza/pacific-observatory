import json
from collections import namedtuple

import pytest

from prices import cc_resolve

pytestmark = pytest.mark.unit

Src = namedtuple("Src", "region subregion country spider")
SOURCES = [
    Src("eap", "sub", "australia", "alpha"),
    Src("eca", "sub", "greece", "beta"),
]
CONFIGS = {
    "alpha": {"prefix": "alpha.com/p/", "path_re": ""},
    "beta": {"prefix": "beta.com/p/", "path_re": ""},
}


def _fake_records(n, host):
    return [
        {
            "url": f"http://{host}/p/{i}",
            "timestamp": f"2020010100000{i}",
            "filename": "crawl/x.warc.gz",
            "offset": i * 10,
            "length": 10,
            "digest": f"D{i}",
        }
        for i in range(n)
    ]


@pytest.fixture
def patched(monkeypatch):
    def fake_query(index, prefix, path_re, **kw):
        host = prefix.split("/")[0]
        return _fake_records(2, host)

    monkeypatch.setattr("prices.cc_index.query_prefix", fake_query)


def test_a_crawl_resolves_every_source_into_one_file(tmp_path, patched):
    written = cc_resolve.resolve_index("CC-MAIN-2020-01", SOURCES, CONFIGS, tmp_path)
    assert written == 4
    rows = [
        json.loads(ln)
        for ln in (tmp_path / "by_index" / "CC-MAIN-2020-01.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {r["spider"] for r in rows} == {"alpha", "beta"}
    # The fetch side needs these and nothing from cluster.idx.
    for field in ("url", "timestamp", "filename", "offset", "length", "cc_index"):
        assert field in rows[0]


def test_resume_sees_only_completed_crawls(tmp_path, patched):
    cc_resolve.resolve_index("CC-MAIN-2020-01", SOURCES, CONFIGS, tmp_path)
    # A partial file left by an interrupt must not read as done.
    (tmp_path / "by_index" / ".CC-MAIN-2020-05.jsonl.tmp").write_text("{}\n")
    assert cc_resolve.resolved_indexes(tmp_path) == ["CC-MAIN-2020-01"]


def test_one_broken_source_does_not_lose_the_rest_of_the_crawl(tmp_path, monkeypatch):
    def flaky(index, prefix, path_re, **kw):
        if prefix.startswith("alpha"):
            raise RuntimeError("cdx block fetch failed")
        return _fake_records(3, "beta.com")

    monkeypatch.setattr("prices.cc_index.query_prefix", flaky)
    written = cc_resolve.resolve_index("CC-MAIN-2020-01", SOURCES, CONFIGS, tmp_path)
    # The crawl's parse is already paid for; beta's records must survive alpha.
    assert written == 3


def test_consolidate_regroups_crawls_into_per_source_manifests(tmp_path, patched):
    for index in ("CC-MAIN-2020-01", "CC-MAIN-2020-05"):
        cc_resolve.resolve_index(index, SOURCES, CONFIGS, tmp_path)
    counts = cc_resolve.consolidate(tmp_path)
    assert counts == {"alpha": 4, "beta": 4}
    alpha = (tmp_path / "by_source" / "alpha.jsonl").read_text(encoding="utf-8")
    assert alpha.count("\n") == 4
    assert "beta" not in alpha
