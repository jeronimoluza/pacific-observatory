"""Custom rich progress columns for `python run.py text build`.

Row layout (left to right):
    [i/N]  <bar-20>  unit-name  done/total  rate art/s  country-elapsed  total-elapsed  ETA

A single Progress task is reset per unit so the bar reflects within-country
keywording progress (advanced per-source, weighted by raw news.csv row count).
ETA is derived from the rolling rate over completed country units against the
sum of pre-scanned country article counts.
"""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, Task
from rich.text import Text


def count_csv_rows(news_csv: Path) -> int:
    """Cheap row count using a single-column CSV read.

    Returns 0 on any read failure; the bar then degrades gracefully (this
    source contributes nothing to the per-unit total).
    """
    try:
        return len(
            pd.read_csv(news_csv, usecols=["date"], encoding="utf-8", low_memory=False)
        )
    except Exception:
        return 0


def _fmt_secs(secs: float) -> str:
    return str(timedelta(seconds=int(max(0, secs))))


class UnitIdxColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        idx = task.fields.get("unit_idx", 0)
        ut = task.fields.get("unit_total", 0)
        return Text(f"[{idx}/{ut}]", style="cyan")


class UnitNameColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        return Text(f"{task.fields.get('unit_name', ''):<28}")


class ArticleCounterColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        done = int(task.completed)
        total = int(task.total or 0)
        return Text(f"{done:>9,}/{total:<9,}")


class RateColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        elapsed = task.elapsed or 0
        if elapsed <= 0 or task.completed <= 0:
            return Text("    — art/s")
        rate = float(task.completed) / float(elapsed)
        return Text(f"{rate:>5.0f} art/s")


class CountryElapsedColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        return Text(f"{_fmt_secs(task.elapsed or 0)} cty")


class TotalElapsedColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        build_start = task.fields.get("build_start", time.time())
        return Text(f"{_fmt_secs(time.time() - build_start)} tot")


class EtaColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        articles_done_completed = task.fields.get("articles_done_completed", 0)
        total_articles_all = task.fields.get("total_articles_all", 0)
        build_start = task.fields.get("build_start", time.time())
        count_in_total = task.fields.get("count_in_total", True)
        elapsed = time.time() - build_start
        articles_done = articles_done_completed + (
            int(task.completed) if count_in_total else 0
        )
        if elapsed <= 0 or articles_done <= 0 or total_articles_all <= 0:
            return Text("ETA   —  ")
        rate = articles_done / elapsed
        remaining = max(0, total_articles_all - articles_done)
        return Text(f"ETA {_fmt_secs(remaining / rate)}")


def make_build_progress(console: Console) -> Progress:
    return Progress(
        UnitIdxColumn(),
        BarColumn(bar_width=20),
        UnitNameColumn(),
        ArticleCounterColumn(),
        RateColumn(),
        CountryElapsedColumn(),
        TotalElapsedColumn(),
        EtaColumn(),
        console=console,
    )
