"""Click CLI for erd-smith."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table as RichTable
from rich.text import Text

from . import __version__
from .diagram import generate_diagram
from .differ import diff_schemas
from .linter import LintLevel, lint_schema
from .orm_parser import parse_orm
from .parser import parse_sql

console = Console()


def _load_schema(path: str, orm: str | None = None):
    p = Path(path)
    if not p.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        sys.exit(1)
    source = p.read_text(encoding="utf-8")
    if orm:
        return parse_orm(source, orm)
    suffix = p.suffix.lower()
    if suffix == ".sql":
        return parse_sql(source)
    elif suffix == ".py":
        if "models.Model" in source:
            return parse_orm(source, "django")
        elif "Column(" in source or "mapped_column(" in source:
            return parse_orm(source, "sqlalchemy")
        else:
            return parse_orm(source, "sqlalchemy")
    else:
        return parse_sql(source)


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """erd-smith: Auto-generate database ERD diagrams."""


@cli.command()
@click.argument("schema_file", type=click.Path(exists=True))
@click.option("--orm", type=click.Choice(["django", "sqlalchemy"]), default=None)
@click.option("--format", "fmt", type=click.Choice(["mermaid", "plantuml", "dot"]), default="mermaid")
@click.option("--output", "-o", type=click.Path(), default=None)
def generate(schema_file: str, orm: str | None, fmt: str, output: str | None) -> None:
    """Generate ERD diagram from a schema file."""
    schema = _load_schema(schema_file, orm)
    if not schema.tables:
        console.print("[yellow]No tables found.[/yellow]")
        return
    console.print(f"[green]Parsed {len(schema.tables)} table(s)[/green]")
    content = generate_diagram(schema, fmt)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]Written to {output}[/green]")
    else:
        click.echo(content)


@cli.command()
@click.argument("old_schema", type=click.Path(exists=True))
@click.argument("new_schema", type=click.Path(exists=True))
@click.option("--orm", type=click.Choice(["django", "sqlalchemy"]), default=None)
@click.option("--format", "fmt", type=click.Choice(["terminal", "json", "markdown"]), default="terminal")
def diff(old_schema: str, new_schema: str, orm: str | None, fmt: str) -> None:
    """Compare two schema files."""
    old = _load_schema(old_schema, orm)
    new = _load_schema(new_schema, orm)
    result = diff_schemas(old, new)
    if fmt == "json":
        click.echo(json.dumps(result.to_dict(), indent=2))
    elif fmt == "markdown":
        click.echo(result.to_markdown())
    else:
        if not result.has_changes:
            console.print("[green]No differences found.[/green]")
            return
        if result.added_tables:
            console.print("[green]Added tables:[/green]")
            for t in result.added_tables:
                console.print(f"  + {t}")
        if result.removed_tables:
            console.print("[red]Removed tables:[/red]")
            for t in result.removed_tables:
                console.print(f"  - {t}")
        for td in result.modified_tables:
            console.print(f"\n[yellow]Modified: {td.table_name}[/yellow]")
            for c in td.added_columns:
                console.print(f"  [green]+ {c}[/green]")
            for c in td.removed_columns:
                console.print(f"  [red]- {c}[/red]")
            for c in td.modified_columns:
                console.print(f"  [yellow]~ {c.name}[/yellow]: {c.change}")


@cli.command()
@click.argument("schema_file", type=click.Path(exists=True))
@click.option("--orm", type=click.Choice(["django", "sqlalchemy"]), default=None)
@click.option("--format", "fmt", type=click.Choice(["terminal", "json"]), default="terminal")
def lint(schema_file: str, orm: str | None, fmt: str) -> None:
    """Lint a schema file for best practices."""
    schema = _load_schema(schema_file, orm)
    issues = lint_schema(schema)
    if fmt == "json":
        click.echo(json.dumps([i.to_dict() for i in issues], indent=2))
        return
    if not issues:
        console.print("[green]No lint issues found.[/green]")
        return
    table = RichTable(title="Schema Lint Results", border_style="yellow")
    table.add_column("Rule", style="bold")
    table.add_column("Level")
    table.add_column("Table")
    table.add_column("Column")
    table.add_column("Message")
    level_styles = {LintLevel.ERROR: "bold red", LintLevel.WARNING: "yellow", LintLevel.INFO: "blue"}
    for issue in issues:
        style = level_styles.get(issue.level, "dim")
        table.add_row(issue.rule, Text(issue.level.value, style=style), issue.table,
                      issue.column or "-", issue.message[:70])
    console.print(table)
    errors = sum(1 for i in issues if i.level == LintLevel.ERROR)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    cli()
