from prices.enrich.text_mining import report


def test_md_table_header_and_separator():
    rows = [
        {"country": "philippines", "channel": "supermarket", "n": 12},
        {"country": "japan", "channel": "aggregator", "n": 9},
    ]
    out = report.md_table(rows, columns=["country", "channel", "n"])
    lines = out.strip().splitlines()
    assert lines[0] == "| country | channel | n |"
    sep_cells = [c for c in lines[1].split("|") if c.strip()]
    assert len(sep_cells) == 3
    assert all(set(c.strip()) <= {"-", ":"} for c in sep_cells)
    assert "philippines" in lines[2]
    assert "japan" in lines[3]


def test_md_table_infers_columns_from_first_row():
    rows = [{"a": 1, "b": 2}]
    out = report.md_table(rows)
    assert out.strip().splitlines()[0] == "| a | b |"


def test_md_table_empty_returns_no_rows_line():
    out = report.md_table([])
    assert "no rows" in out.lower()


def test_md_table_empty_with_columns_does_not_raise():
    out = report.md_table([], columns=["a", "b"])
    assert isinstance(out, str)
    assert "no rows" in out.lower()


def test_md_section_heading_levels():
    assert report.md_section("Layer 0", 1) == "# Layer 0"
    assert report.md_section("Sub", 3) == "### Sub"


def test_md_slice_block_renders_subsections_and_tables():
    slices = {
        ("philippines", "supermarket"): [{"name": "rice", "n": 3}],
        ("japan", "aggregator"): [{"name": "soy", "n": 2}],
    }
    out = report.md_slice_block("By country x channel", slices, level=2)
    assert "## By country x channel" in out
    assert "philippines" in out and "japan" in out
    assert "| name | n |" in out
