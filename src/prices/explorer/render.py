"""Splice the payload, the vendored Chart.js and the app script into one file.

Chart.js is inlined rather than pulled from a CDN because the WB intranet
blocks cdn.jsdelivr.net — the dashboard has to work offline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from prices.explorer.aggregate import REPO_ROOT, build_payload

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "_template.html"
APP_JS = HERE / "_app.js"
VENDOR_CHART_JS = (
    REPO_ROOT / "src" / "text" / "plotting" / "vendor" / "chart.umd.min.js"
)
OUT_HTML = REPO_ROOT / "outputs" / "prices" / "global_prices_explorer.html"


def render(payload: dict) -> str:
    html = TEMPLATE.read_text()
    blob = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    # Guard against a product name closing the inline <script> block.
    blob = blob.replace("</", "<\\/")
    html = html.replace("/*__CHART_JS__*/", VENDOR_CHART_JS.read_text())
    html = html.replace("/*__APP_JS__*/", APP_JS.read_text())
    html = html.replace("/*__DATA__*/", blob)
    return html


def run(out_path: Path | None = None) -> Path:
    payload = build_payload()
    out = Path(out_path) if out_path else OUT_HTML
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(payload))
    meta = payload["meta"]
    logger.info(
        "explorer written: %s (%.1f MB) — %s countries, %s nodes, %s trusted obs",
        out,
        out.stat().st_size / 1e6,
        meta["n_countries"],
        meta["n_nodes"],
        meta["n_obs"],
    )
    return out
