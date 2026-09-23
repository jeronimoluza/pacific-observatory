"""The keyword schema: every concept heading, group and concept as published.

Built from ``keywords/concepts/*.json`` by ``load_concept_catalog`` and written
by publish to ``outputs/text/dashboard_data/keywords_schema.json``. The
dashboard embeds it, so an exported HTML file carries its own definitions.
"""

import json
from pathlib import Path

from text.analysis.utils import load_concept_catalog

# Suffixes build_outputs writes per group into uncertainty_attribution/<family>.csv.
_ATTRIBUTION_SUFFIXES = ("absolute", "framing", "intensity")


def _columns(family: str, key: str) -> dict:
    return {
        f"epu/{family}_epu.csv": [f"EPU_{key}_index"],
        f"uncertainty_attribution/{family}.csv": [
            f"{key}_{s}{z}" for s in _ATTRIBUTION_SUFFIXES for z in ("", "_z")
        ],
    }


def build_keywords_schema() -> dict:
    catalog = load_concept_catalog()
    headings = {}
    for heading, h in catalog["headings"].items():
        # `concepts` and `groups` list only direct children; a group's series
        # still counts every concept beneath it, at any depth.
        groups = {
            gid: {
                "label": catalog["groups"][gid].get("label", gid),
                "parent": catalog["groups"][gid].get("parent"),
                "groups": [
                    k for k in h["groups"] if catalog["groups"][k].get("parent") == gid
                ],
                "concepts": [
                    cid
                    for cid in h["concepts"]
                    if catalog["concepts"][cid].get("group") == gid
                    and not catalog["concepts"][cid].get("deprecated")
                ],
                "columns": _columns("groups", gid),
            }
            for gid in h["groups"]
        }
        concepts = {
            cid: {
                "label": c.get("label", cid),
                "group": c.get("group"),
                "forms": c["forms"],
                "review": c.get("review", {}),
                "columns": _columns("concepts", cid),
            }
            for cid in h["concepts"]
            if not (c := catalog["concepts"][cid]).get("deprecated")
        }
        headings[heading] = {
            "label": h["label"],
            "groups": groups,
            "concepts": concepts,
        }
    return {"headings": headings}


def write_keywords_schema(out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(build_keywords_schema(), f, ensure_ascii=False, indent=2)
    return out_path
