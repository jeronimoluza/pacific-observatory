"""Product enrichment pipeline (concatenate → prepare → classify → merge)."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

__version__ = "1.0.0-dev"
