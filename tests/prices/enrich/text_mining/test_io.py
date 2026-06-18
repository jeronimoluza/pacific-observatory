import pandas as pd
import polars as pl
import pytest

from prices.enrich import config
from prices.enrich.text_mining import io


def test_report_dir_under_text_mining():
    assert io.REPORT_DIR == config.ENRICH_DIR / "_text_mining"
    assert "_text_mining" in str(io.REPORT_DIR)


def test_ensure_report_dir_creates_only_report_dir(tmp_path, monkeypatch):
    target = tmp_path / "_enrich" / "_text_mining"
    monkeypatch.setattr(io, "REPORT_DIR", target)
    assert not target.exists()
    returned = io.ensure_report_dir()
    assert returned == target
    assert target.is_dir()
    # idempotent
    assert io.ensure_report_dir() == target


def test_write_markdown_writes_under_report_dir(tmp_path, monkeypatch):
    target = tmp_path / "_text_mining"
    monkeypatch.setattr(io, "REPORT_DIR", target)
    path = io.write_markdown("layer0_corpus_probe.md", "# hello\n")
    assert path == target / "layer0_corpus_probe.md"
    assert path.read_text(encoding="utf-8") == "# hello\n"


def test_write_markdown_rejects_non_md(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "REPORT_DIR", tmp_path / "_text_mining")
    with pytest.raises(ValueError):
        io.write_markdown("report.txt", "x")


@pytest.mark.parametrize(
    "bad_name",
    ["../escape.md", "/abs/path.md", "sub/../../escape.md", "../../etc/passwd.md"],
)
def test_write_markdown_rejects_out_of_dir(bad_name, tmp_path, monkeypatch):
    monkeypatch.setattr(io, "REPORT_DIR", tmp_path / "_text_mining")
    with pytest.raises(ValueError):
        io.write_markdown(bad_name, "x")


def test_write_parquet_writes_under_report_dir(tmp_path, monkeypatch):
    target = tmp_path / "_text_mining"
    monkeypatch.setattr(io, "REPORT_DIR", target)
    frame = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = io.write_parquet("f5_within_leaf_dispersion.parquet", frame)
    assert path == target / "f5_within_leaf_dispersion.parquet"
    back = pd.read_parquet(path)
    assert list(back.columns) == ["a", "b"]
    assert len(back) == 2


def test_write_parquet_rejects_out_of_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "REPORT_DIR", tmp_path / "_text_mining")
    with pytest.raises(ValueError):
        io.write_parquet("../escape.parquet", pd.DataFrame({"a": [1]}))


def test_write_parquet_rejects_non_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "REPORT_DIR", tmp_path / "_text_mining")
    with pytest.raises(ValueError):
        io.write_parquet("table.md", pd.DataFrame({"a": [1]}))


def _make_products_input(path):
    df = pl.DataFrame(
        {
            "product_name_original": ["Coca-Cola 1.5L x6", "Fresh Lettuce"],
            "category": ["beverages", "produce"],
            "country": ["philippines", "philippines"],
            "currency": ["PHP", "PHP"],
            "lang": ["en", "en"],
            "channel": ["supermarket", "supermarket"],
            "declared_coicop_codes": ["01.2.2", "01.1.7"],
            "price": [240.0, 30.0],
            "n_rows": [12, 4],
        }
    )
    df.write_parquet(path)


def _make_products(path):
    df = pl.DataFrame(
        {
            "product_identity_key": ["k1", "k2"],
            "first_name": ["Coca-Cola 1.5L x6", "Fresh Lettuce"],
            "canonical_loose": ["coca cola", "lettuce"],
            "country": ["philippines", "philippines"],
            "lang": ["en", "en"],
            "brand": ["coca-cola", None],
            "count": [6, 1],
            "value": [1.5, 1.0],
            "unit": ["L", "item"],
            "category": ["beverages", "produce"],
            "channel": ["supermarket", "supermarket"],
            "price": [240.0, 30.0],
            "n_observations": [12, 4],
            "input_hashes": [["h1", "h2"], ["h3"]],
        }
    )
    df.write_parquet(path)


def test_read_products_input_default_columns(tmp_path, monkeypatch):
    p = tmp_path / "products_input.parquet"
    _make_products_input(p)
    monkeypatch.setattr(config, "PRODUCTS_INPUT_PARQUET", p)
    frame = io.read_products_input()
    cols = set(frame.columns)
    assert cols == {
        "product_name_original",
        "country",
        "channel",
        "lang",
        "price",
        "n_rows",
    }


def test_read_products_input_explicit_columns(tmp_path, monkeypatch):
    p = tmp_path / "products_input.parquet"
    _make_products_input(p)
    monkeypatch.setattr(config, "PRODUCTS_INPUT_PARQUET", p)
    frame = io.read_products_input(["product_name_original", "country"])
    assert set(frame.columns) == {"product_name_original", "country"}


def test_read_products_excludes_input_hashes_by_default(tmp_path, monkeypatch):
    p = tmp_path / "products.parquet"
    _make_products(p)
    monkeypatch.setattr(config, "PRODUCTS_PARQUET", p)
    frame = io.read_products()
    assert "input_hashes" not in frame.columns


def test_read_products_explicit_columns(tmp_path, monkeypatch):
    p = tmp_path / "products.parquet"
    _make_products(p)
    monkeypatch.setattr(config, "PRODUCTS_PARQUET", p)
    frame = io.read_products(["first_name", "canonical_loose"])
    assert set(frame.columns) == {"first_name", "canonical_loose"}
