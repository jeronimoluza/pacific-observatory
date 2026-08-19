import pytest

from prices import cc_index

pytestmark = pytest.mark.unit


def _write_fake_cluster(directory, index, rows=50):
    path = directory / f"cluster_{index}.idx"
    lines = [
        f"com,example)/p/{i} 20200101000000\tcdx-00000.gz\t{i * 100}\t100\t1\n"
        for i in range(rows)
    ]
    path.write_text("".join(lines), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _clear_cache():
    cc_index._CLUSTER_CACHE.clear()
    yield
    cc_index._CLUSTER_CACHE.clear()


def test_resident_clusters_are_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(cc_index, "cache_dir", lambda *a, **k: tmp_path)
    names = [f"CC-MAIN-20{n:02d}-01" for n in range(13, 26)]
    for name in names:
        _write_fake_cluster(tmp_path, name)
        cc_index.load_cluster(name)
        # A backfill walks 103 of these and each costs ~0.3 GB parsed. Holding
        # them all is what took a 4 GB machine down mid-run.
        assert len(cc_index._CLUSTER_CACHE) <= cc_index._CLUSTER_MAX_RESIDENT

    assert list(cc_index._CLUSTER_CACHE) == names[-cc_index._CLUSTER_MAX_RESIDENT :]


def test_a_cached_cluster_is_still_served_from_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(cc_index, "cache_dir", lambda *a, **k: tmp_path)
    path = _write_fake_cluster(tmp_path, "CC-MAIN-2020-01")
    keys_first, _ = cc_index.load_cluster("CC-MAIN-2020-01")

    # Deleting the file proves the second call did not re-read from disk.
    path.unlink()
    keys_again, _ = cc_index.load_cluster("CC-MAIN-2020-01")
    assert keys_again == keys_first


def test_reuse_refreshes_recency_so_the_active_index_is_not_evicted(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(cc_index, "cache_dir", lambda *a, **k: tmp_path)
    for name in ("A", "B", "C"):
        _write_fake_cluster(tmp_path, name)

    cc_index.load_cluster("A")
    cc_index.load_cluster("B")
    cc_index.load_cluster("A")  # touch A so B becomes the oldest
    cc_index.load_cluster("C")

    assert "A" in cc_index._CLUSTER_CACHE
    assert "B" not in cc_index._CLUSTER_CACHE


def test_enumeration_is_unlimited_by_default(tmp_path, monkeypatch):
    # A bound here truncates discovery itself: URLs past it are never seen, so
    # nothing downstream can tell they existed.
    monkeypatch.setattr(cc_index, "cache_dir", lambda *a, **k: tmp_path)
    import inspect

    sig = inspect.signature(cc_index.query_prefix)
    assert sig.parameters["max_blocks"].default is None
