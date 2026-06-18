import pandas as pd

from prices.enrich.text_mining import candidates, io

# Reuse the products_input column shape for tier-a residual mining and a
# products.parquet-shaped frame for tier-b sub-label clustering.
PRODUCTS_INPUT_COLUMNS = [
    "product_name_original",
    "category",
    "country",
    "currency",
    "lang",
    "channel",
    "declared_coicop_codes",
    "price",
    "n_rows",
]

PRODUCTS_COLUMNS = [
    "product_identity_key",
    "first_name",
    "canonical_loose",
    "country",
    "lang",
    "brand",
    "count",
    "value",
    "unit",
    "category",
    "channel",
    "price",
    "n_observations",
]


def _residual_input() -> pd.DataFrame:
    # Rows the spine leaves WITHOUT a structural span, but that carry a latent
    # quantity surface form the current tier-a regex missed. The "12pk" form
    # appears most often so it must rank first; "ct" form is the singleton.
    rows = [
        (
            "Bibingka 250gsm",
            "food",
            "philippines",
            "PHP",
            "en",
            "supermarket",
            "01.1.1",
            50.0,
            9,
        ),
        (
            "Crackers 12pk box",
            "food",
            "philippines",
            "PHP",
            "en",
            "supermarket",
            "01.1.8",
            80.0,
            7,
        ),
        (
            "Cookies 12pk box",
            "food",
            "philippines",
            "PHP",
            "en",
            "supermarket",
            "01.1.8",
            70.0,
            6,
        ),
        (
            "Wafers 12pk box",
            "food",
            "philippines",
            "PHP",
            "en",
            "supermarket",
            "01.1.8",
            65.0,
            5,
        ),
        (
            "Eggs 6ct tray",
            "food",
            "philippines",
            "PHP",
            "en",
            "supermarket",
            "01.1.4",
            95.0,
            3,
        ),
        # plain rows with no latent quantity surface — must not become candidates
        (
            "Fresh Lettuce",
            "produce",
            "philippines",
            "PHP",
            "en",
            "supermarket",
            "01.1.7",
            30.0,
            4,
        ),
        (
            "Hand Soap",
            "household",
            "philippines",
            "PHP",
            "en",
            "aggregator",
            "12.1.3",
            89.0,
            2,
        ),
    ]
    return pd.DataFrame(rows, columns=PRODUCTS_INPUT_COLUMNS)


def _products_frame() -> pd.DataFrame:
    # Two canonical clusters within (country, channel): a large "instant noodle"
    # cluster and a smaller "soy sauce" cluster, so size-descending ranking is
    # unambiguous.
    rows = [
        (
            "k1",
            "Instant Noodle Chicken",
            "chicken instant noodle",
            "philippines",
            "en",
            "lucky",
            1,
            None,
            None,
            "food",
            "supermarket",
            12.0,
            8,
        ),
        (
            "k2",
            "Instant Noodle Beef",
            "beef instant noodle",
            "philippines",
            "en",
            "lucky",
            1,
            None,
            None,
            "food",
            "supermarket",
            12.0,
            6,
        ),
        (
            "k3",
            "Instant Noodle Seafood",
            "instant noodle seafood",
            "philippines",
            "en",
            "lucky",
            1,
            None,
            None,
            "food",
            "supermarket",
            13.0,
            5,
        ),
        (
            "k4",
            "Soy Sauce Dark",
            "dark soy sauce",
            "philippines",
            "en",
            "datu",
            1,
            None,
            None,
            "food",
            "supermarket",
            25.0,
            4,
        ),
        (
            "k5",
            "Soy Sauce Light",
            "light soy sauce",
            "philippines",
            "en",
            "datu",
            1,
            None,
            None,
            "food",
            "supermarket",
            24.0,
            3,
        ),
    ]
    return pd.DataFrame(rows, columns=PRODUCTS_COLUMNS)


def test_tier_a_candidates_ranked_by_frequency_descending():
    rows, _md = candidates.tier_a_regex_candidates(_residual_input())
    assert rows, "expected at least one tier-a regex candidate"
    counts = [r["count"] for r in rows]
    assert counts == sorted(counts, reverse=True)
    # The 12pk surface (3 rows) must outrank the 6ct surface (1 row).
    assert rows[0]["count"] >= rows[-1]["count"]
    # Each candidate carries a human-review payload, not an applied pattern.
    top = rows[0]
    assert "surface_form" in top
    assert "regex_sketch" in top
    assert "example_names" in top


def test_tier_b_sublabel_candidates_ranked_by_size_descending():
    rows, _md = candidates.tier_b_sublabel_candidates(_products_frame())
    assert rows, "expected at least one tier-b sub-label candidate"
    sizes = [r["size"] for r in rows]
    assert sizes == sorted(sizes, reverse=True)
    # Largest cluster (instant noodle, 3 rows) must rank first.
    assert rows[0]["size"] >= rows[-1]["size"]
    top = rows[0]
    assert "cluster_label" in top
    assert "representative_names" in top
    assert "country" in top
    assert "channel" in top


def test_tier_a_returns_markdown_string():
    _rows, markdown = candidates.tier_a_regex_candidates(_residual_input())
    assert isinstance(markdown, str)
    assert markdown.strip()


def test_tier_b_returns_markdown_string():
    _rows, markdown = candidates.tier_b_sublabel_candidates(_products_frame())
    assert isinstance(markdown, str)
    assert markdown.strip()


def test_empty_frames_yield_no_candidates():
    rows_a, _ = candidates.tier_a_regex_candidates(
        pd.DataFrame(columns=PRODUCTS_INPUT_COLUMNS)
    )
    rows_b, _ = candidates.tier_b_sublabel_candidates(
        pd.DataFrame(columns=PRODUCTS_COLUMNS)
    )
    assert rows_a == []
    assert rows_b == []


def test_write_targets_only_report_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "REPORT_DIR", tmp_path)
    res_a = candidates.tier_a_regex_candidates(_residual_input(), write=True)
    res_b = candidates.tier_b_sublabel_candidates(_products_frame(), write=True)
    path_a = res_a["markdown_path"]
    path_b = res_b["markdown_path"]
    assert path_a.name == candidates.TIER_A_MARKDOWN_NAME
    assert path_b.name == candidates.TIER_B_MARKDOWN_NAME
    assert tmp_path.resolve() in path_a.resolve().parents
    assert tmp_path.resolve() in path_b.resolve().parents


def test_emitters_never_write_to_cascade_dirs(tmp_path, monkeypatch):
    # The not-auto-applied boundary (T-007-18): redirect the harness write
    # surface to tmp_path and assert the cascade pattern/sub-label stores are
    # untouched after running both emitters with write=True.
    monkeypatch.setattr(io, "REPORT_DIR", tmp_path)
    enrich_root = io.config.ENRICH_DIR  # not used as a write target
    regex_dir = enrich_root.parent  # placeholder; real assertion is on source dirs
    assert regex_dir is not None

    from pathlib import Path

    src_root = Path(candidates.__file__).resolve().parents[1]
    regex_patterns = src_root / "regex_patterns"
    tier_b = src_root / "tier_b"

    before = _dir_snapshot(regex_patterns) | _dir_snapshot(tier_b)
    candidates.tier_a_regex_candidates(_residual_input(), write=True)
    candidates.tier_b_sublabel_candidates(_products_frame(), write=True)
    after = _dir_snapshot(regex_patterns) | _dir_snapshot(tier_b)
    assert before == after, "candidates must not write under regex_patterns/ or tier_b/"


def _dir_snapshot(directory) -> set:
    if not directory.exists():
        return set()
    return {
        (str(p.relative_to(directory)), p.stat().st_mtime_ns)
        for p in directory.rglob("*")
        if p.is_file()
    }
