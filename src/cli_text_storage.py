"""Click commands for two-tier text storage (archive / restore / storage-status).

Kept in a separate module so `cli.py` stays under the 500-line cap. The
`register(text_group, opts)` function attaches the three commands to the
existing `text` subgroup, reusing the shared option decorators from cli.py.
"""

import click


def register(text_group, opts: dict):
    """Attach archive/restore/storage-status commands to a click group.

    `opts` carries the shared decorators from cli.py:
        region, subregion, country, source
    so we don't duplicate validators or help strings.
    """
    region_opt = opts["region"]
    subregion_opt = opts["subregion"]
    country_opt = opts["country"]
    source_opt = opts["source"]

    @text_group.command("archive")
    @region_opt
    @subregion_opt
    @country_opt
    @source_opt
    @click.option(
        "--path",
        "path_",
        default=None,
        help="Explicit path under data/text/ (overrides region/subregion/country)",
    )
    @click.option(
        "--news-only",
        is_flag=True,
        help="Sync news.csv + urls.csv only (cheap update for already-archived scope)",
    )
    def text_archive(region, subregion, country, source, path_, news_only):
        """Copy local data/text/<scope> to /Volumes/SSKJL/data/text/<scope>."""
        from core.storage_tier import (
            archive_scope,
            ensure_drive_mounted,
            resolve_scope,
        )
        from core.storage_tier_format import describe_scope, format_archive_summary

        try:
            ensure_drive_mounted()
        except RuntimeError as exc:
            raise click.ClickException(str(exc))

        try:
            pairs = resolve_scope(
                region=region,
                subregion=subregion,
                country=country,
                source=source,
                path=path_,
            )
        except (ValueError, KeyError) as exc:
            raise click.ClickException(str(exc))

        scope_label = describe_scope(region, subregion, country, source, path_)
        click.echo(f"  Archive scope: {scope_label}")
        for local_dir, drive_dir in pairs:
            click.echo(f"    {local_dir} → {drive_dir}")
        if news_only:
            click.echo("  Mode: --news-only (news.csv + urls.csv only)")

        try:
            result = archive_scope(pairs, news_only=news_only)
        except (RuntimeError, FileNotFoundError) as exc:
            raise click.ClickException(str(exc))

        click.echo(format_archive_summary(result, pairs, scope_label))
        if not result["ok"]:
            raise SystemExit(1)

    @text_group.command("restore")
    @region_opt
    @subregion_opt
    @country_opt
    @source_opt
    @click.option(
        "--path",
        "path_",
        default=None,
        help="Explicit path under data/text/ (overrides region/subregion/country)",
    )
    def text_restore(region, subregion, country, source, path_):
        """Copy /Volumes/SSKJL/data/text/<scope> back to local data/text/<scope>."""
        from core.storage_tier import (
            ensure_drive_mounted,
            resolve_scope,
            restore_scope,
        )
        from core.storage_tier_format import describe_scope, format_restore_summary

        try:
            ensure_drive_mounted()
        except RuntimeError as exc:
            raise click.ClickException(str(exc))

        try:
            pairs = resolve_scope(
                region=region,
                subregion=subregion,
                country=country,
                source=source,
                path=path_,
            )
        except (ValueError, KeyError) as exc:
            raise click.ClickException(str(exc))

        scope_label = describe_scope(region, subregion, country, source, path_)
        click.echo(f"  Restore scope: {scope_label}")
        for local_dir, drive_dir in pairs:
            click.echo(f"    {drive_dir} → {local_dir}")

        try:
            result = restore_scope(pairs)
        except (RuntimeError, FileNotFoundError) as exc:
            raise click.ClickException(str(exc))

        click.echo(format_restore_summary(result, pairs, scope_label))
        if not result["ok"]:
            raise SystemExit(1)

    @text_group.command("storage-status")
    @region_opt
    @subregion_opt
    @country_opt
    @click.option(
        "--json", "as_json", is_flag=True, help="Emit JSON instead of a table"
    )
    def text_storage_status(region, subregion, country, as_json):
        """Show local-vs-drive state per country (works while drive is offline)."""
        from core.storage_tier import is_drive_online
        from core.storage_tier_format import format_status_json, format_status_table
        from core.storage_tier_status import storage_status

        online = is_drive_online()
        rows = storage_status(
            region=region, subregion=subregion, country=country, drive_online=online
        )
        if as_json:
            click.echo(format_status_json(rows, online))
        else:
            click.echo()
            click.echo(format_status_table(rows, online))
            click.echo()
