"""
Report generation orchestration for CPI analysis.

Generates timestamped report outputs and refreshes reports/latest/ for the dashboard.

Usage:
    poetry run python src/cpi/analysis/run_reports.py
    poetry run python src/cpi/analysis/run_reports.py --input path/to/data.csv --outdir path/to/reports
"""

import argparse
import sys
from pathlib import Path

# Handle both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate CPI analysis reports from supermarket price data."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/cpi/analysis/all_countries_supermarket_prices.csv",
        help="Path to input CSV file (default: data/cpi/analysis/all_countries_supermarket_prices.csv)",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="data/cpi/analysis/reports",
        help="Output directory for reports (default: data/cpi/analysis/reports)",
    )
    parser.add_argument(
        "--no-latest",
        action="store_true",
        help="Skip updating the latest/ directory",
    )
    return parser.parse_args()


def run_reports(input_path: str, outdir: str, update_latest: bool = True):
    """
    Generate all reports and write to timestamped directory.

    Args:
        input_path: Path to input CSV file
        outdir: Base output directory for reports
        update_latest: Whether to update the latest/ symlink/directory
    """
    pass


def main():
    """Main entry point."""
    args = parse_args()
    run_reports(
        input_path=args.input,
        outdir=args.outdir,
        update_latest=not args.no_latest,
    )


if __name__ == "__main__":
    main()
