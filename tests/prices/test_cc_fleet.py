"""The fleet preflight, which exists so nobody launches a half-parsing run.

Instances are keyless and unreachable by design, so a bundle missing parse tiers
is only visible hours later in a shipped log, as a low yield that reads like
Common Crawl being thin. Counting the tiers first is the whole point.
"""

import pytest

from prices import cc_fleet

pytestmark = pytest.mark.unit

BUNDLER = """
import sys
SRC = "somewhere/"
DEST = sys.argv[1]
FILES = [
    ("archived.py", "archived.py"),
    ("archived_microdata.py", "archived_microdata.py"),
    ("archived_bysource.py", "archived_bysource.py"),
]
"""


@pytest.fixture
def kit(tmp_path):
    script = tmp_path / "bundle_parse.py"
    script.write_text(BUNDLER)
    src = tmp_path / "price_scraping"
    src.mkdir()
    return {"script": script, "src": src}


def have(kit, *names):
    for name in names:
        (kit["src"] / name).write_text("")


def pin_preflight(monkeypatch, kit):
    """Point run()'s preflight at the fixture kit. The original is bound before
    patching — a lambda that calls cc_fleet.preflight would call itself."""
    real = cc_fleet.preflight
    monkeypatch.setattr(
        cc_fleet, "preflight", lambda *a, **k: real(kit["src"], kit["script"])
    )


def test_the_bundle_list_is_read_without_importing_it(kit):
    """bundle_parse reads sys.argv at module level, so importing it here would
    pick up pytest's argv."""
    assert cc_fleet.bundle_modules(kit["script"]) == [
        "archived.py",
        "archived_microdata.py",
        "archived_bysource.py",
    ]


def test_a_complete_checkout_passes_preflight(kit):
    have(kit, "archived.py", "archived_microdata.py", "archived_bysource.py")
    check = cc_fleet.preflight(kit["src"], kit["script"])
    assert check["ok"] is True
    assert check["missing"] == []


def test_a_missing_tier_is_named_not_counted(kit):
    have(kit, "archived.py")
    check = cc_fleet.preflight(kit["src"], kit["script"])
    assert check["ok"] is False
    assert check["missing"] == ["archived_microdata.py", "archived_bysource.py"]
    assert check["present"] == ["archived.py"]


def test_an_absent_bundler_is_not_silently_ok(kit, tmp_path):
    """No bundler means nothing to ship, which must not read as 'complete'."""
    check = cc_fleet.preflight(kit["src"], tmp_path / "gone.py")
    assert check["ok"] is False
    assert check["wanted"] == 0


def test_a_run_refuses_while_tiers_are_missing(monkeypatch, kit):
    have(kit, "archived.py")
    pin_preflight(monkeypatch, kit)
    with pytest.raises(RuntimeError, match="2 of 3 parse tiers"):
        cc_fleet.run(backend="ec2", instances=4)


def test_allow_partial_proceeds_and_says_so(monkeypatch, kit, capsys):
    have(kit, "archived.py")
    pin_preflight(monkeypatch, kit)
    out = cc_fleet.run(backend="ec2", instances=4, allow_partial=True)
    assert out["backend"] == "ec2"
    assert "MISSING archived_bysource.py" in capsys.readouterr().out


@pytest.fixture
def complete(monkeypatch, kit):
    have(kit, "archived.py", "archived_microdata.py", "archived_bysource.py")
    pin_preflight(monkeypatch, kit)
    return kit


def test_staging_a_fleet_launches_nothing(complete, tmp_path):
    out = cc_fleet.run(backend="ec2", instances=6, out_dir=tmp_path)
    joined = " ".join(out["commands"])
    assert "launch_fleet.sh 0 6" in joined
    assert "cc-guardrails.yaml" in joined
    # printed, not executed: no instance exists after this call
    assert all(isinstance(c, str) for c in out["commands"])


def test_the_guardrails_stack_comes_before_the_fleet(complete, tmp_path):
    """The budget and the scoped IAM role have to exist before anything bills."""
    commands = cc_fleet.run(backend="ec2", out_dir=tmp_path)["commands"]
    assert "cloudformation" in commands[0]
    assert "launch_fleet" in commands[-1]


def test_local_runs_the_same_fetcher_without_a_bucket(complete, tmp_path):
    out = cc_fleet.run(backend="local", out_dir=tmp_path)
    joined = " ".join(out["commands"])
    assert "ccfetch.py" in joined
    assert "OUT_BUCKET" not in joined  # unset is what keeps output on disk
    assert "aws " not in joined


def test_local_bundles_the_parse_tiers_first(complete, tmp_path):
    commands = cc_fleet.run(backend="local", out_dir=tmp_path)["commands"]
    assert "bundle_parse.py" in commands[0]
    assert "ccfetch.py" in commands[1]


def test_an_unknown_backend_is_refused(complete, tmp_path):
    with pytest.raises(ValueError, match="nonesuch"):
        cc_fleet.run(backend="nonesuch", out_dir=tmp_path)
