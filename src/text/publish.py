"""Text publish stage: generate EPU dashboards and charts."""

import click


def run_publish(region=None, yes=False):
    """Generate EPU dashboards."""
    click.echo()
    click.echo("  Text publish (dashboards)")
    click.echo("  " + "-" * 40)
    if region:
        click.echo(f"  Region: {region}")
    else:
        click.echo("  All regions")
    click.echo()

    if not yes:
        click.confirm("  Proceed?", abort=True)

    try:
        from text.plotting.small_dashboard_integrated import generate_dashboard

        # generate_dashboard() requires explicit data arguments (output_dir,
        # topic_data, etc.) that are not yet assembled here.  Pass region for
        # when the data-loading layer is wired up.
        generate_dashboard(region=region)
    except ImportError:
        click.echo("  Plotting module not yet migrated. Skipping.")
    except TypeError:
        click.echo("  Publish data loading not yet wired. Skipping.")
    except Exception as e:
        click.echo(f"  Error: {e}")
