import pytest

from prices import cc_config

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear():
    cc_config.resolve_cc_indexes.cache_clear()
    yield
    cc_config.resolve_cc_indexes.cache_clear()


def _break_collinfo(monkeypatch):
    class _Dead:
        stdout = "<html>504 Gateway Timeout</html>"

    monkeypatch.setattr(cc_config.subprocess, "run", lambda *a, **k: _Dead())


def test_strict_refuses_to_silently_shrink_the_crawl_set(monkeypatch):
    # The fallback is 8 recent crawls against the ~123 a full backfill needs.
    # Returning it on a transient 504 turns "all the history we can get" into
    # "the last few months" while still reporting success.
    _break_collinfo(monkeypatch)
    with pytest.raises(RuntimeError, match="truncate history"):
        cc_config.resolve_cc_indexes(2013, strict=True)


def test_non_strict_still_falls_back_for_offline_use(monkeypatch):
    _break_collinfo(monkeypatch)
    got = cc_config.resolve_cc_indexes(2013, strict=False)
    assert got == cc_config._FALLBACK_CC_INDEXES
