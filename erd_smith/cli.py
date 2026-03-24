"""Click CLI for erd-smith: auto-generate ERD diagrams from schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table as RichTable

from . import __version__
from .diagram import to_mermaid, to_dot, to_ascii, to_dbml
from .differ import diff_schemas
from .linter import lint_schema
from .parsers.base import Schema
from .parsers.sql_parser import SqlParser
from .parsers.django_parser import DjangoParser

console = Console()
PARSERS = [SqlParser(), DjangoParser()]


def _detect_and_parse(source: str, orm: str | None = None) -> Schema:
    if orm:
        if orm.lower() == "django":
            return DjangoParser().parse(source)
        return SqlParser().parse(source)
    for parser in PARSERS:
        if parser.can_parse(source):
            return parser.parse(source)
    console.print("[red]Cannot detect schema format. Use --orm.[/red]")
    sys.exit(1)


@click.group()
@click.version_option(version=__version__)
def cli():
    """erd-smith: Auto-generate ERD diagrams from database schemas."""


@cli.command()
@click.argument("schema_file", type=click.Path(exists=True))
@click.option("--orm", type=click.Choice(["sql", "django"], case_sensitive=False), default=None)
@click.option("--format", "fmt", type=click.Choice(["mermaid", "dot", "ascii", "dbml", "json"]), default="mermaid")
@click.option("--output", "-o", type=click.Path(), default=None)
def generate(schema_file: str, orm: str | None, fmt: str, output: str | None):
    """Generate ERD diagram from a schema file."""
    source = Path(schema_file).read_text(encoding="utf-8")
    schema = _detect_and_parse(source, orm)
    if not schema.tables:
        console.print("[yellow]No tables found.[/yellow]")
        return
    fmts = {"mermaid": to_mermaid, "dot": to_dot, "ascii": to_ascii, "dbml": to_dbml}
    result = json.dumps(schema.to_dict(), indent=2) if fmt == "json" else fmts[fmt](schema)
    if output:
        Path(output).write_text(result, encoding="utf-8")
        console.print(f"[green]Written to {output}[/green]")
    else:
        console.print(result)
    console.print(f"\n[dim]{len(schema.tables)} tables, {len(schema.relationships)} relationships[/dim]")


@cli.command()
@click.argument("old_schema", type=click.Path(exists=True))
@click.argument("new_schema", type=click.Path(exists=True))
@click.option("--orm", type=click.Choice(["sql", "django"], case_sensitive=False), default=None)
@click.option("--format", "fmt", type=click.Choice(["rich", "json"]), default="rich")
def diff(old_schema: str, new_schema: str, orm: str | None, fmt: str):
    """Compare two schema files."""
    old = _detect_and_parse(Path(old_schema).read_text(encoding="utf-8"), orm)
    new = _detect_and_parse(Path(new_schema).read_text(encoding="utf-8"), orm)
    result = diff_schemas(old, new)
    if fmt == "json":
        click.echo(json.dumps(result.to_dict(), indent=2))
        return
    if not result.has_changes:
        console.print("[green]No differences.[/green]")
        return
    console.print(f"[bold]Schema Diff:[/bold] {result.summary()}\n")
    for t in result.added_tables:
        console.print(f"  [green]+[/green] {t}")
    for t in result.removed_tables:
        console.print(f"  [red]-[/red] {t}")
    for td in result.modified_tables:
        console.print(f"\n[yellow]~ {td.table_name}[/yellow]")
        for c in td.added_columns:
            console.print(f"    [green]+ {c}[/green]")
        for c in td.removed_columns:
            console.print(f"    [red]- {c}[/red]")
        for c in td.modified_columns:
            console.print(f"    [yellow]~ {c.name}: {c.change} ({c.old_value} -> {c.new_value})[/yellow]")


@cli.command()
@click.argument("schema_file", type=click.Path(exists=True))
@click.option("--orm", type=click.Choice(["sql", "django"], case_sensitive=False), default=None)
@click.option("--format", "fmt", type=click.Choice(["rich", "json"]), default="rich")
def lint(schema_file: str, orm: str | None, fmt: str):
    """Lint a schema for best practices."""
    source = Path(schema_file).read_text(encoding="utf-8")
    schema = _detect_and_parse(source, orm)
    issues = lint_schema(schema)
    if fmt == "json":
        click.echo(json.dumps([i.to_dict() for i in issues], indent=2))
        return
    if not issues:
        console.print("[green]No lint issues.[/green]")
        return
    table = RichTable(title=f"Schema Lint ({len(issues)} issues)")
    table.add_column("Rule", style="cyan", width=8)
    table.add_column("Level", width=8)
    table.add_column("Table")
    table.add_column("Message")
    styles = {"error": "[red]error[/red]", "warning": "[yellow]warn[/yellow]", "info": "[blue]info[/blue]"}
    for i in issues:
        table.add_row(i.rule, styles.get(i.level, i.level), i.table, i.message)
    console.print(table)
    if any(i.level == "error" for i in issues):
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
