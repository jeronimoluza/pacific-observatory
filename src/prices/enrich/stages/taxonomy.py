import asyncio
import json
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic_ai import Agent

from prices.enrich import config
from prices.enrich.schemas import LeafSubcategories, SubcategoryEntry


def _load_leaves() -> pd.DataFrame:
    """Return depth-3 COICOP leaves (codes matching '^\\d{2}\\.\\d\\.\\d$')."""
    df = pd.read_excel(config.COICOP_XLSX)
    return df[df["code"].astype(str).str.match(r"^\d{2}\.\d\.\d$", na=False)]


def _split_field(value) -> list[str]:
    if pd.isna(value):
        return []
    return [s.strip() for s in str(value).split(";") if s.strip()]


def _load_food_depth4() -> dict[str, list[SubcategoryEntry]]:
    """Division 01 (food): use official depth-4 leaves as the sub_label_id vocabulary.

    Each depth-3 parent (e.g. "01.1.1") gets entries built from depth-4 children
    (e.g. "01.1.1.1") plus the mandatory trailing "_other" escape hatch.
    """
    df = pd.read_excel(config.COICOP_XLSX)
    food = df[df["code"].astype(str).str.match(r"^01\.\d\.\d\.\d$", na=False)]
    out: dict[str, list[SubcategoryEntry]] = {}
    for _, row in food.iterrows():
        parent = ".".join(str(row["code"]).split(".")[:3])
        out.setdefault(parent, []).append(
            SubcategoryEntry(
                id=str(row["code"]).replace(".", "-"),
                label=str(row["title"]),
                synonyms=[],
            )
        )
    for entries in out.values():
        entries.append(SubcategoryEntry(id="_other", label="Other", synonyms=[]))
    return out


def _build_agent() -> Agent:
    return Agent(
        f"google-gla:{config.MODEL_NAME}",
        output_type=LeafSubcategories,
        system_prompt=config.TAXONOMY_PROMPT_PATH.read_text(),
        output_retries=config.OUTPUT_RETRIES,
    )


async def _ask_leaf(agent: Agent, leaf_row: pd.Series) -> LeafSubcategories:
    payload = {
        "coicop_code": str(leaf_row["code"]),
        "title": str(leaf_row.get("title", "")),
        "intro": "" if pd.isna(leaf_row.get("intro")) else str(leaf_row["intro"]),
        "includes": _split_field(leaf_row.get("includes")),
        "also_includes": _split_field(leaf_row.get("alsoIncludes")),
        "excludes": _split_field(leaf_row.get("excludes")),
    }
    result = await agent.run(json.dumps(payload))
    return result.output


async def _run_async() -> dict:
    leaves = _load_leaves()
    food = _load_food_depth4()
    food_parents = set(food.keys())
    nonfood = leaves[~leaves["code"].isin(food_parents)]

    agent = _build_agent()
    sem = asyncio.Semaphore(config.CONCURRENCY)

    async def fetch(row: pd.Series) -> tuple[str, list[dict]]:
        async with sem:
            try:
                sub = await _ask_leaf(agent, row)
                entries = [e.model_dump() for e in sub.entries]
                if not entries or entries[-1]["id"] != "_other":
                    entries.append({"id": "_other", "label": "Other", "synonyms": []})
                return str(row["code"]), entries
            except Exception as e:
                print(f"FAIL {row['code']}: {e}")
                return str(row["code"]), [
                    {"id": "_other", "label": "Other", "synonyms": []}
                ]

    results = await asyncio.gather(*(fetch(r) for _, r in nonfood.iterrows()))

    out: dict[str, list[dict]] = {}
    for code, entries in results:
        out[code] = entries
    for code, entries in food.items():
        out[code] = [e.model_dump() for e in entries]

    return out


def run(out_path: Optional[Path] = None) -> dict:
    out_path = out_path or config.COICOP_SUBCATS_JSON
    data = asyncio.run(_run_async())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
