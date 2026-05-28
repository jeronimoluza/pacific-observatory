import asyncio
import json
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic_ai import Agent

from prices.enrich import config
from prices.enrich.schemas import LeafSubcategories


def _clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).replace("_x000D_", "").strip()


def _split_field(value) -> list[str]:
    if pd.isna(value):
        return []
    raw = str(value).replace("_x000D_", "\n")
    parts: list[str] = []
    for chunk in raw.replace(";", "\n").splitlines():
        s = chunk.lstrip("*").strip()
        if s:
            parts.append(s)
    return parts


def _load_leaves() -> pd.DataFrame:
    """Return the deepest-available COICOP leaves.

    A leaf is any code in the xlsx that no other code uses as a prefix. In
    COICOP 2018 this resolves to a mix of depth-4 (no depth-5 children) and
    depth-5 entries — yielding the most specific node available per branch.
    """
    df = pd.read_excel(config.COICOP_XLSX)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    codes = set(df["code"])
    is_leaf = df["code"].apply(
        lambda c: not any(other != c and other.startswith(c + ".") for other in codes)
    )
    return df[is_leaf].reset_index(drop=True)


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
        "title": _clean_text(leaf_row.get("title")),
        "intro": _clean_text(leaf_row.get("intro")),
        "includes": _split_field(leaf_row.get("includes")),
        "also_includes": _split_field(leaf_row.get("alsoIncludes")),
        "excludes": _split_field(leaf_row.get("excludes")),
    }
    result = await agent.run(json.dumps(payload))
    return result.output


async def _run_async() -> dict:
    leaves = _load_leaves()
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

    results = await asyncio.gather(*(fetch(r) for _, r in leaves.iterrows()))
    return {code: entries for code, entries in results}


def run(out_path: Optional[Path] = None) -> dict:
    out_path = out_path or config.COICOP_SUBCATS_JSON
    data = asyncio.run(_run_async())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
