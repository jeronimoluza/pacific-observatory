import pytest

from prices.cc_samples import SampleKeeper

pytestmark = pytest.mark.unit


def test_per_year_cap_is_enforced(tmp_path):
    keeper = SampleKeeper(tmp_path, per_year=2)
    kept = [
        keeper.offer("<html>a</html>", "http://x/1", "20190101000000"),
        keeper.offer("<html>b</html>", "http://x/2", "20190202000000"),
        keeper.offer("<html>c</html>", "http://x/3", "20190303000000"),
    ]
    assert kept == [True, True, False]
    assert len(list((tmp_path / "2019").glob("*.html"))) == 2


def test_years_have_independent_budgets(tmp_path):
    keeper = SampleKeeper(tmp_path, per_year=1)
    assert keeper.offer("<html>a</html>", "http://x/1", "20190101000000")
    assert keeper.offer("<html>b</html>", "http://x/2", "20240101000000")
    assert (tmp_path / "2019").exists() and (tmp_path / "2024").exists()


def test_a_rerun_does_not_refill_a_year_already_full(tmp_path):
    SampleKeeper(tmp_path, per_year=1).offer(
        "<html>a</html>", "http://x/1", "20190101000000"
    )
    assert not SampleKeeper(tmp_path, per_year=1).offer(
        "<html>b</html>", "http://x/2", "20190505000000"
    )
    assert len(list((tmp_path / "2019").glob("*.html"))) == 1


def test_url_is_recoverable_from_the_manifest(tmp_path):
    keeper = SampleKeeper(tmp_path, per_year=2)
    keeper.offer("<html>a</html>", "http://x/product/42", "20190101000000")
    body = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8")
    assert "http://x/product/42" in body


def test_oversized_page_is_truncated(tmp_path):
    keeper = SampleKeeper(tmp_path, per_year=1, max_bytes=100)
    keeper.offer("x" * 5000, "http://x/1", "20190101000000")
    path = next((tmp_path / "2019").glob("*.html"))
    assert len(path.read_text(encoding="utf-8")) == 100


def test_unparseable_timestamp_is_declined(tmp_path):
    keeper = SampleKeeper(tmp_path, per_year=3)
    assert not keeper.offer("<html>a</html>", "http://x/1", "")
    assert not keeper.offer("<html>a</html>", "http://x/1", "notadate")
