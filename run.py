"""Thin wrapper so `python run.py` works without installing the package.

Usage:
    python run.py text collect --country ukraine --max-pages 3
    python run.py text build --country ukraine
    python run.py --help
"""

import sys
from pathlib import Path

# Add src/ to the import path so modules resolve without `pip install -e .`
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cli import main

if __name__ == "__main__":
    main()
