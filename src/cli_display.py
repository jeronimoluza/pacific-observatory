import sys
from pathlib import Path


def command_prefix():
    return "python run.py" if Path(sys.argv[0]).name == "run.py" else "po"


def _example_lines(title, commands):
    lines = [f"  {title}:"]
    for command, description in commands:
        lines.append(f"    {command_prefix()} {command:<40} {description}")
    return lines


def top_level_help_examples():
    return "\n".join(
        ["\b"]
        + _example_lines(
            "Start Here",
            [
                ("list-regions", "Show region/subregion/country topology"),
                (
                    "text collect --list --country <slug>",
                    "List configured newspaper keys",
                ),
                ("text collect --country <slug> --dry-run", "Preview a scrape safely"),
            ],
        )
    )


def text_help_examples():
    return "\n".join(
        ["\b"]
        + _example_lines(
            "Start Here",
            [
                (
                    "text collect --list --country <slug>",
                    "List configured newspaper keys",
                ),
                ("text collect --country <slug> --dry-run", "Preview a scrape safely"),
            ],
        )
        + _example_lines(
            "Typical Workflow",
            [
                ("text collect --country <slug>", "Scrape a single country"),
                ("text build --country <slug>", "Compute EPU outputs"),
                ("text publish --country <slug>", "Generate dashboards"),
            ],
        )
    )
