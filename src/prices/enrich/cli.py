import click


@click.group(name="process")
def process_group():
    """AI enrichment pipeline (prepare → taxonomy → enrich → merge)."""


@process_group.command()
def prepare():
    raise NotImplementedError  # Task 2.1


@process_group.command()
def taxonomy():
    raise NotImplementedError  # Task 3.1


@process_group.command()
def enrich():
    raise NotImplementedError  # Task 2.4


@process_group.command()
def merge():
    raise NotImplementedError  # Task 5.1
