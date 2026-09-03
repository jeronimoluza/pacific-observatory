import pandas as pd
import pytest
from click.testing import CliRunner

from prices.enrich import cli, shards

pytestmark = pytest.mark.unit


@pytest.fixture
def calls(monkeypatch):
    """Record what each stage was invoked with instead of running it."""
    seen = {}
    monkeypatch.setattr(
        cli.concatenate_stage,
        "run",
        lambda **kw: seen.setdefault("concatenate", kw),
    )
    monkeypatch.setattr(
        cli.prepare_shards, "run", lambda **kw: seen.setdefault("prepare", kw)
    )
    monkeypatch.setitem(cli.STAGES, "classify", lambda: seen.setdefault("classify", {}))
    monkeypatch.setitem(cli.STAGES, "merge", lambda: seen.setdefault("merge", {}))
    return seen


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    frame = pd.DataFrame(
        {
            "product_name": ["Rice"],
            "price": ["10"],
            "currency": ["FJD"],
            "country": ["fiji"],
            "source": ["shop_a"],
        }
    )
    for rel in ("eap/pacific/fiji/shop_a", "ssa/western/ghana/esoko"):
        shards.write_shard(frame, tmp_path / f"{rel}.parquet")
    monkeypatch.setattr(cli.concatenate_stage, "PER_SOURCE_DIR", tmp_path)
    return tmp_path


def invoke(*args):
    return CliRunner().invoke(cli.process_command, list(args))


def test_no_selector_runs_every_stage_unscoped(calls):
    result = invoke()
    assert result.exit_code == 0
    assert set(calls) == {"concatenate", "prepare", "classify", "merge"}
    assert calls["concatenate"]["selectors"] is None
    assert calls["prepare"]["selectors"] is None
    assert "warning" not in result.output


def test_only_is_passed_to_the_scoped_stages(calls):
    result = invoke("--only", "ssa", "--stage", "prepare")
    assert result.exit_code == 0
    assert calls["prepare"]["selectors"] == ["ssa"]


def test_only_is_repeatable(calls):
    invoke("--only", "ssa", "--only", "**/agmarknet", "--stage", "concatenate")
    assert calls["concatenate"]["selectors"] == ["ssa", "**/agmarknet"]


def test_region_country_flags_become_a_selector(calls):
    invoke("-r", "eap", "-c", "fiji", "--stage", "prepare")
    assert calls["prepare"]["selectors"] == ["eap/*/fiji"]


def test_flags_and_only_compose(calls):
    invoke("--only", "ssa", "-c", "fiji", "--stage", "prepare")
    assert calls["prepare"]["selectors"] == ["ssa", "*/*/fiji"]


def test_workers_reach_the_sharded_stage(calls):
    invoke("--workers", "4", "--stage", "prepare")
    assert calls["prepare"]["workers"] == 4


def test_a_scoped_run_says_which_stages_ignore_the_scope(calls):
    result = invoke("--only", "ssa")
    assert "classify, merge" in result.output


def test_no_warning_when_only_scoped_stages_run(calls):
    result = invoke("--only", "ssa", "--stage", "prepare")
    assert "warning" not in result.output


def test_explain_reports_the_match_and_runs_nothing(calls, corpus):
    result = invoke("--explain", "--only", "ssa")
    assert result.exit_code == 0
    assert "1 shards in 1 countries" in result.output
    assert "ssa/western/ghana" in result.output
    assert calls == {}


def test_explain_without_a_selector_covers_the_corpus(calls, corpus):
    result = invoke("--explain")
    assert "2 shards in 2 countries" in result.output


def test_explain_says_so_when_nothing_matches(calls, corpus):
    result = invoke("--explain", "--only", "antarctica")
    assert "no shards match" in result.output
    assert calls == {}
