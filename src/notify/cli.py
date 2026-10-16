"""`po notify`: send one alert through the configured backend."""

from __future__ import annotations

import click

from notify.send import SEVERITIES, notify


@click.command("notify")
@click.option("--severity", "-s", type=click.Choice(SEVERITIES), default="info", show_default=True)
@click.argument("message", nargs=-1, required=True)
def notify_command(severity: str, message: tuple[str, ...]):
    """Send MESSAGE as one alert (telegram, or the file fallback; src/configs/notify.yaml)."""
    click.echo(notify(severity, " ".join(message)))
