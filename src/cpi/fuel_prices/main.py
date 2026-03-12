"""Backward-compatible entry point for the fuel_prices CLI."""

from .cli import main

__all__ = ["main"]


if __name__ == "__main__":
    main()
