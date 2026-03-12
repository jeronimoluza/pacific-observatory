"""Command handlers for the fuel_prices CLI."""

from .collect import cmd_backfill_fuelcheck, cmd_fetch, cmd_kr_news, cmd_th_news
from .normalize import cmd_normalize
from .publish import cmd_publish

__all__ = [
    "cmd_backfill_fuelcheck",
    "cmd_fetch",
    "cmd_kr_news",
    "cmd_normalize",
    "cmd_publish",
    "cmd_th_news",
]
