"""`prices explorer` must be able to ship a region-scoped build from the CLI.

`render.run` and `build_payload` have taken a region since they were written;
only the CLI could not say so, which made the regional dashboard reachable
solely by calling Python directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

from click.testing import CliRunner

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import cli  # noqa: E402


def _invoke(args):
    return CliRunner().invoke(cli.po, args)


def test_explorer_exposes_region():
    out = _invoke(["prices", "explorer", "--help"]).output
    assert "--region" in out
    assert "-r," in out


def test_explorer_rejects_an_unknown_region():
    r = _invoke(["prices", "explorer", "--region", "not-a-region"])
    assert r.exit_code != 0
    assert "unknown region" in r.output


def test_explorer_threads_the_region_through_to_render(monkeypatch):
    seen = {}

    def fake_run(out_path=None, region=None):
        seen["out"] = out_path
        seen["region"] = region
        return Path("/dev/null")

    import prices.explorer as explorer

    monkeypatch.setattr(explorer, "run", fake_run)
    r = _invoke(["prices", "explorer", "--region", "eap", "--out", "/tmp/x.html"])
    assert r.exit_code == 0, r.output
    assert seen == {"out": "/tmp/x.html", "region": "eap"}


def test_explorer_without_region_still_builds_the_world(monkeypatch):
    seen = {}
    import prices.explorer as explorer

    monkeypatch.setattr(
        explorer, "run", lambda out_path=None, region=None: seen.update(region=region)
    )
    r = _invoke(["prices", "explorer"])
    assert r.exit_code == 0, r.output
    assert seen["region"] is None
