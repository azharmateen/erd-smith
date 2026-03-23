"""Schema lint: naming conventions, missing indexes, orphan tables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .parser import Schema


class LintLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class LintIssue:
    rule: str
    level: LintLevel
    table: str
    column: str | None
    message: str

    def to_dict(self) -> dict:
        d = {"rule": self.rule, "level": self.level.value, "table": self.table, "message": self.message}
        if self.column:
            d["column"] = self.column
        return d


def _is_snake_case(name: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", name))


def lint_schema(schema: Schema) -> list[LintIssue]:
    issues: list[LintIssue] = []
    related_tables: set[str] = set()
    for table in schema.tables:
        for fk in table.foreign_keys:
            related_tables.add(table.name.lower())
            related_tables.add(fk.ref_table.lower())
        for col in table.columns:
            if col.references:
                related_tables.add(table.name.lower())
                related_tables.add(col.references.split(".")[0].lower())
    indexed_cols: dict[str, set[str]] = {}
    for table in schema.tables:
        cols: set[str] = set()
        cols.update(c.lower() for c in table.primary_key)
        for idx in table.indexes:
            cols.update(c.lower() for c in idx.columns)
        for col in table.columns:
            if col.unique:
                cols.add(col.name.lower())
        indexed_cols[table.name.lower()] = cols
    for table in schema.tables:
        if not _is_snake_case(table.name):
            issues.append(LintIssue(rule="ES001", level=LintLevel.WARNING, table=table.name, column=None,
                                    message=f"Table '{table.name}' should use snake_case naming"))
        if not table.primary_key:
            issues.append(LintIssue(rule="ES004", level=LintLevel.ERROR, table=table.name, column=None,
                                    message=f"Table '{table.name}' has no primary key"))
        if table.name.lower() not in related_tables and len(schema.tables) > 1:
            issues.append(LintIssue(rule="ES006", level=LintLevel.INFO, table=table.name, column=None,
                                    message=f"Table '{table.name}' has no relationships (orphan table)"))
        tbl_indexed = indexed_cols.get(table.name.lower(), set())
        for col in table.columns:
            if not _is_snake_case(col.name):
                issues.append(LintIssue(rule="ES002", level=LintLevel.WARNING, table=table.name, column=col.name,
                                        message=f"Column '{col.name}' should use snake_case naming"))
            if col.references and not col.name.endswith("_id"):
                issues.append(LintIssue(rule="ES003", level=LintLevel.WARNING, table=table.name, column=col.name,
                                        message=f"FK column '{col.name}' should end with '_id'"))
            if col.references and col.name.lower() not in tbl_indexed:
                issues.append(LintIssue(rule="ES005", level=LintLevel.WARNING, table=table.name, column=col.name,
                                        message=f"FK column '{col.name}' should have an index"))
    return issues
