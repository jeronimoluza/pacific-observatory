from prices.tools.cc_slice import _cap, _url_path


def test_a_capped_slice_still_spans_every_crawl():
    # The whole point of a slice is that it reaches across years. Taking the
    # first N records instead would spend the entire budget inside whichever
    # crawl happens to sort first and produce a "time series" with one point.
    by_crawl = {
        "CC-MAIN-2014-23": [f"a{i}\n" for i in range(500)],
        "CC-MAIN-2019-26": [f"b{i}\n" for i in range(500)],
        "CC-MAIN-2026-25": [f"c{i}\n" for i in range(2)],
    }
    kept = _cap(by_crawl, 30)
    assert len(kept) == 30
    assert {ln[0] for ln in kept} == {"a", "b", "c"}


def test_an_uncapped_slice_keeps_everything():
    by_crawl = {"CC-MAIN-2019-26": ["x\n", "y\n"]}
    assert len(_cap(by_crawl, 0)) == 2
    assert len(_cap(by_crawl, 99)) == 2


def test_a_crawl_that_runs_out_does_not_stall_the_budget():
    # One crawl with a single record used to leave the round-robin cycling on
    # an empty list, returning fewer records than asked for in silence.
    by_crawl = {"a": ["1\n"], "b": [f"b{i}\n" for i in range(50)]}
    assert len(_cap(by_crawl, 20)) == 20


def test_terms_match_the_path_not_the_host():
    # A host such as coca-cola-shop.example would otherwise drag its whole
    # catalogue into every slice, whatever the pages actually sell.
    assert _url_path("https://coca-cola-shop.example/p/1234") == "p/1234"
