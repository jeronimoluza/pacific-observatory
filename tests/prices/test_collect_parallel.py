"""Hermetic tests for the `prices collect -P N` process-parallel driver.

No network and no writes outside tmp_path: children are a stub `run.py` planted
in a fake project root, so the real command builder is exercised end to end.
"""

from __future__ import annotations

import json
import textwrap
import time
from pathlib import Path

import pytest

from prices import collect_parallel as cp
from prices.config import PriceSourceConfig


def _manifest(country, source, region="lac", role=None):
    return PriceSourceConfig(
        scaffolding="spider",
        spider=source,
        channel=None,
        analytical_role=role,
        region=region,
        subregion="sub",
        country=country,
        source=source,
        config_path=f"{region}/sub/{country}/{source}.yaml",
    )


def _write_ledger(run_dir: Path, records: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "status.jsonl", "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _stub_run_py(project_root: Path, body: str) -> None:
    """Plant a fake run.py that mimics `prices collect --country X --source Y`."""
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "run.py").write_text(
        textwrap.dedent(
            """
            import sys
            args = sys.argv[1:]
            country = args[args.index("--country") + 1]
            source = args[args.index("--source") + 1]
            """
        )
        + textwrap.dedent(body)
    )


# --- command construction -------------------------------------------------


def test_child_command_targets_one_source_and_disables_nesting():
    cmd = cp.child_command(
        Path("/repo"), _manifest("peru", "plazavea_pe"), max_items=None
    )

    assert cmd[1:] == [
        "/repo/run.py",
        "prices",
        "collect",
        "--country",
        "peru",
        "--source",
        "plazavea_pe",
        "--parallel",
        "1",
    ]


def test_child_command_forwards_max_items():
    cmd = cp.child_command(
        Path("/repo"), _manifest("peru", "plazavea_pe"), max_items=500
    )

    assert cmd[-2:] == ["--max-items", "500"]


# --- prior-run ledger -----------------------------------------------------


def test_prior_status_reads_every_wave_and_keeps_slowest_measurement(tmp_path):
    logs = tmp_path / "logs" / "prices"
    _write_ledger(
        logs / "_fullrun_20260101_000000",
        [
            {"country": "peru", "source": "a", "status": "ok", "secs": 100},
            {"country": "peru", "source": "b", "status": "timeout", "secs": 5400},
        ],
    )
    _write_ledger(
        logs / "_fullrun_20260102_000000",
        [
            {"country": "peru", "source": "a", "status": "ok_norows", "secs": 40},
            {"country": "peru", "source": "c", "status": "fail", "secs": 7},
        ],
    )

    done, measured = cp.prior_status(tmp_path)

    assert done == {("peru", "a")}
    assert measured[("peru", "a")] == 100
    assert measured[("peru", "b")] == 5400
    assert ("peru", "c") in measured


def test_prior_status_tolerates_a_truncated_ledger(tmp_path):
    logs = tmp_path / "logs" / "prices" / "_fullrun_20260101_000000"
    logs.mkdir(parents=True)
    (logs / "status.jsonl").write_text(
        '{"country": "peru", "source": "a", "status": "ok", "secs": 5}\n{"country": "pe'
    )

    done, measured = cp.prior_status(tmp_path)

    assert done == {("peru", "a")}


# --- longest-first ordering ----------------------------------------------


def test_order_puts_measured_sources_ahead_of_unmeasured_guesses():
    manifests = [
        _manifest("peru", "unmeasured_but_huge"),
        _manifest("peru", "measured_and_quick"),
    ]
    measured = {("peru", "measured_and_quick"): 5.0}
    sizes = {("peru", "unmeasured_but_huge"): 500_000_000}

    ordered = cp.order_sources(manifests, measured=measured, sizes=sizes)

    assert [m.source for m in ordered] == ["measured_and_quick", "unmeasured_but_huge"]


def test_order_is_longest_first_within_measured_sources():
    manifests = [_manifest("peru", "quick"), _manifest("peru", "slow")]
    measured = {("peru", "quick"): 10.0, ("peru", "slow"): 9000.0}

    ordered = cp.order_sources(manifests, measured=measured, sizes={})

    assert [m.source for m in ordered] == ["slow", "quick"]


def test_brand_new_source_gets_the_median_footprint_not_last_place():
    manifests = [
        _manifest("peru", "tiny"),
        _manifest("peru", "brand_new"),
        _manifest("peru", "big"),
    ]
    sizes = {("peru", "tiny"): 10, ("peru", "big"): 10_000}

    ordered = cp.order_sources(manifests, measured={}, sizes=sizes)

    assert [m.source for m in ordered] == ["big", "brand_new", "tiny"]


# --- the pool -------------------------------------------------------------


def test_run_parallel_banks_a_status_row_per_source(tmp_path):
    project_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    _stub_run_py(
        project_root,
        """
        import pathlib
        out = pathlib.Path(sys.argv[0]).parent.parent / "data" / "prices"
        d = out / "lac" / "sub" / country / source
        d.mkdir(parents=True, exist_ok=True)
        p = d / "price_observations.csv"
        p.write_text("header\\nrow1\\nrow2\\n")
        """,
    )

    run_dir = cp.run_parallel(
        [_manifest("peru", "alpha"), _manifest("chile", "beta")],
        workers=2,
        timeout=60,
        project_root=project_root,
        data_root=data_root,
    )

    records = [
        json.loads(line) for line in (run_dir / "status.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2
    assert {r["source"] for r in records} == {"alpha", "beta"}
    assert {r["status"] for r in records} == {"ok"}
    assert {r["new_rows"] for r in records} == {2}


def test_run_parallel_marks_a_clean_run_with_no_new_rows(tmp_path):
    project_root = tmp_path / "repo"
    _stub_run_py(project_root, "pass\n")

    run_dir = cp.run_parallel(
        [_manifest("peru", "alpha")],
        workers=1,
        timeout=60,
        project_root=project_root,
        data_root=tmp_path / "data",
    )

    record = json.loads((run_dir / "status.jsonl").read_text().strip())
    assert record["status"] == "ok_norows"
    assert record["new_rows"] == 0


def test_run_parallel_records_a_nonzero_exit_as_fail(tmp_path):
    project_root = tmp_path / "repo"
    _stub_run_py(project_root, "sys.exit(2)\n")

    run_dir = cp.run_parallel(
        [_manifest("peru", "alpha")],
        workers=1,
        timeout=60,
        project_root=project_root,
        data_root=tmp_path / "data",
    )

    record = json.loads((run_dir / "status.jsonl").read_text().strip())
    assert record["status"] == "fail"
    assert record["rc"] == 2


def test_run_parallel_kills_a_hung_source_at_the_timeout(tmp_path):
    project_root = tmp_path / "repo"
    _stub_run_py(project_root, "import time\ntime.sleep(120)\n")

    started = time.time()
    run_dir = cp.run_parallel(
        [_manifest("peru", "hung")],
        workers=1,
        timeout=1,
        project_root=project_root,
        data_root=tmp_path / "data",
    )
    elapsed = time.time() - started

    record = json.loads((run_dir / "status.jsonl").read_text().strip())
    assert record["status"] == "timeout"
    assert elapsed < 60


def test_run_parallel_actually_overlaps_children(tmp_path):
    project_root = tmp_path / "repo"
    _stub_run_py(project_root, "import time\ntime.sleep(2)\n")
    manifests = [_manifest("c%d" % i, "s%d" % i) for i in range(4)]

    started = time.time()
    cp.run_parallel(
        manifests,
        workers=4,
        timeout=60,
        project_root=project_root,
        data_root=tmp_path / "data",
    )
    elapsed = time.time() - started

    assert elapsed < 6, "4 x 2s children at -P 4 should not serialize into 8s"


def test_resume_skips_pairs_already_collected_in_a_prior_wave(tmp_path):
    project_root = tmp_path / "repo"
    _stub_run_py(project_root, "pass\n")
    _write_ledger(
        project_root / "logs" / "prices" / "_fullrun_20260101_000000",
        [{"country": "peru", "source": "alpha", "status": "ok", "secs": 3}],
    )

    run_dir = cp.run_parallel(
        [_manifest("peru", "alpha"), _manifest("chile", "beta")],
        workers=2,
        timeout=60,
        project_root=project_root,
        data_root=tmp_path / "data",
        resume=True,
    )

    records = [
        json.loads(line) for line in (run_dir / "status.jsonl").read_text().splitlines()
    ]
    assert [r["source"] for r in records] == ["beta"]


def test_index_sources_are_counted_from_their_own_csv(tmp_path):
    project_root = tmp_path / "repo"
    _stub_run_py(
        project_root,
        """
        import pathlib
        d = pathlib.Path(sys.argv[0]).parent.parent / "data" / "prices" / "lac" / "sub" / country / source
        d.mkdir(parents=True, exist_ok=True)
        (d / "index_observations.csv").write_text("header\\nrow1\\n")
        """,
    )

    run_dir = cp.run_parallel(
        [_manifest("peru", "cpi_feed", role="cpi_benchmark")],
        workers=1,
        timeout=60,
        project_root=project_root,
        data_root=tmp_path / "data",
    )

    record = json.loads((run_dir / "status.jsonl").read_text().strip())
    assert record["new_rows"] == 1


def test_run_parallel_refuses_to_start_below_the_disk_floor(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    _stub_run_py(project_root, "pass\n")
    monkeypatch.setattr(cp, "MIN_FREE_GB", 10**9)

    with pytest.raises(cp.DiskSpaceError):
        cp.run_parallel(
            [_manifest("peru", "alpha")],
            workers=1,
            timeout=60,
            project_root=project_root,
            data_root=tmp_path / "data",
        )


# --- scoped resume --------------------------------------------------------


def test_resume_scoped_to_one_run_ignores_stale_ledgers(tmp_path):
    project_root = tmp_path / "repo"
    _stub_run_py(project_root, "pass\n")
    logs = project_root / "logs" / "prices"
    _write_ledger(
        logs / "_fullrun_20260101_000000",
        [{"country": "peru", "source": "stale", "status": "ok", "secs": 3}],
    )
    _write_ledger(
        logs / "_fullrun_20260601_000000",
        [{"country": "chile", "source": "today", "status": "ok", "secs": 3}],
    )

    run_dir = cp.run_parallel(
        [_manifest("peru", "stale"), _manifest("chile", "today")],
        workers=2,
        timeout=60,
        project_root=project_root,
        data_root=tmp_path / "data",
        resume=logs / "_fullrun_20260601_000000",
    )

    records = [
        json.loads(line) for line in (run_dir / "status.jsonl").read_text().splitlines()
    ]
    assert [r["source"] for r in records] == ["stale"]


def test_scoped_resume_accepts_the_ledger_file_itself(tmp_path):
    project_root = tmp_path / "repo"
    _stub_run_py(project_root, "pass\n")
    logs = project_root / "logs" / "prices"
    _write_ledger(
        logs / "_fullrun_20260601_000000",
        [{"country": "chile", "source": "today", "status": "ok", "secs": 3}],
    )

    ledgers = cp.resume_ledgers(
        project_root, logs / "_fullrun_20260601_000000" / "status.jsonl"
    )

    assert ledgers == [logs / "_fullrun_20260601_000000" / "status.jsonl"]


def test_bare_resume_still_reads_every_ledger(tmp_path):
    project_root = tmp_path / "repo"
    logs = project_root / "logs" / "prices"
    _write_ledger(logs / "_fullrun_20260101_000000", [{"country": "a", "source": "x"}])
    _write_ledger(logs / "_fullrun_20260601_000000", [{"country": "b", "source": "y"}])

    assert len(cp.resume_ledgers(project_root, cp.RESUME_ALL)) == 2


def test_scoped_resume_rejects_a_missing_run(tmp_path):
    with pytest.raises(cp.ResumeTargetError):
        cp.resume_ledgers(tmp_path, tmp_path / "nope")


def test_cost_ordering_still_uses_every_ledger_under_scoped_resume(tmp_path):
    """A stale ledger is the only place a long pole's runtime is recorded."""
    project_root = tmp_path / "repo"
    logs = project_root / "logs" / "prices"
    _write_ledger(
        logs / "_fullrun_20260101_000000",
        [{"country": "peru", "source": "long_pole", "status": "ok", "secs": 5000}],
    )

    _, measured = cp.prior_status(project_root)

    assert measured[("peru", "long_pole")] == 5000
