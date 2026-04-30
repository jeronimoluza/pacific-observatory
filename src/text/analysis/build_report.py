"""End-of-run build summary.

Captures per-unit results and warnings during a build, then renders the
summary to stdout (rich.Table) and a timestamped markdown file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table


@dataclass
class UnitRow:
    name: str
    level: str
    status: str  # "ok" | "skipped" | "failed"
    n_articles: int = 0
    n_sources: int = 0
    mode: str = "unknown"  # "full" | "incremental" | "reused" | "aggregate" | "skipped"
    runtime_s: float = 0.0
    error: str | None = None


@dataclass
class BuildSummary:
    units: list[UnitRow] = field(default_factory=list)
    excluded_sources: list[tuple[str, str, str]] = field(default_factory=list)
    nan_drops: list[tuple[str, str, int]] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)

    def add_unit(self, row: UnitRow) -> None:
        self.units.append(row)

    def add_excluded(self, unit: str, source: str, reason: str) -> None:
        self.excluded_sources.append((unit, source, reason))

    def add_nan_drop(self, unit: str, source: str, n: int) -> None:
        if n > 0:
            self.nan_drops.append((unit, source, n))

    def add_failure(self, unit: str, error: str) -> None:
        self.failures.append((unit, error))

    # ── Rendering ────────────────────────────────────────────────────

    def render_to_stdout(self, console: Console | None = None) -> None:
        c = console or Console()
        c.print()
        c.rule("Build summary")

        table = Table(show_lines=False)
        table.add_column("Unit")
        table.add_column("Level")
        table.add_column("Status", style="bold")
        table.add_column("Articles", justify="right")
        table.add_column("Sources", justify="right")
        table.add_column("Mode")
        table.add_column("Runtime", justify="right")
        for row in self.units:
            style = (
                "green"
                if row.status == "ok"
                else "yellow"
                if row.status == "skipped"
                else "red"
            )
            table.add_row(
                row.name,
                row.level,
                f"[{style}]{row.status}[/{style}]",
                f"{row.n_articles:,}",
                str(row.n_sources),
                row.mode,
                f"{row.runtime_s:.1f}s",
            )
        c.print(table)

        if self.excluded_sources:
            c.print()
            c.print("[yellow]Sources excluded from baseline:[/yellow]")
            for unit, src, reason in self.excluded_sources:
                c.print(f"  {unit}/{src}: {reason}")

        if self.nan_drops:
            c.print()
            c.print("[yellow]NaN-body drops:[/yellow]")
            for unit, src, n in self.nan_drops:
                c.print(f"  {unit}/{src}: {n:,} rows")

        if self.failures:
            c.print()
            c.print("[red]Failures:[/red]")
            for unit, err in self.failures:
                c.print(f"  {unit}: {err}")

        c.print()

    def render_markdown(self) -> str:
        lines: list[str] = []
        lines.append("# Build report")
        lines.append("")
        lines.append(
            f"_Generated {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_"
        )
        lines.append("")
        lines.append("## Units")
        lines.append("")
        lines.append("| Unit | Level | Status | Articles | Sources | Mode | Runtime |")
        lines.append("|------|-------|--------|----------|---------|------|---------|")
        for row in self.units:
            lines.append(
                "| {} | {} | {} | {:,} | {} | {} | {:.1f}s |".format(
                    row.name,
                    row.level,
                    row.status,
                    row.n_articles,
                    row.n_sources,
                    row.mode,
                    row.runtime_s,
                )
            )
        lines.append("")

        if self.excluded_sources:
            lines.append("## Sources excluded from baseline")
            lines.append("")
            lines.append("| Unit | Source | Reason |")
            lines.append("|------|--------|--------|")
            for unit, src, reason in self.excluded_sources:
                lines.append(f"| {unit} | {src} | {reason} |")
            lines.append("")

        if self.nan_drops:
            lines.append("## NaN-body drops")
            lines.append("")
            lines.append("| Unit | Source | Rows dropped |")
            lines.append("|------|--------|--------------|")
            for unit, src, n in self.nan_drops:
                lines.append(f"| {unit} | {src} | {n:,} |")
            lines.append("")

        if self.failures:
            lines.append("## Failures")
            lines.append("")
            lines.append("| Unit | Error |")
            lines.append("|------|-------|")
            for unit, err in self.failures:
                lines.append(f"| {unit} | {err} |")
            lines.append("")

        return "\n".join(lines)

    def write_markdown(self, output_dir: Path) -> Path:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = output_dir / f"build_report_{ts}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_markdown(), encoding="utf-8")
        return path


# ── Logger setup for the build invocation ────────────────────────────


def setup_build_logger(logs_dir: Path) -> logging.Logger:
    """File logger for the whole text-build invocation.

    Writes to logs/text/build/{date}/{datetime}.log. Console output is
    handled separately by the rich progress bar.
    """
    now = datetime.now(tz=timezone.utc)
    log_dir = logs_dir / "text" / "build" / now.strftime("%Y-%m-%d")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}.log"

    logger = logging.getLogger("po.text.build")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s — %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )
        logger.addHandler(fh)
    return logger
