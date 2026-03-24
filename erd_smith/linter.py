"""Schema lint: naming conventions, missing indexes, orphan tables."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .parsers.base import Schema


@dataclass
class LintIssue:
    rule: str
    level: str
    table: str
    message: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "level": self.level, "table": self.table, "message": self.message}


SQL_KEYWORDS = {"user", "order", "group", "select", "table", "index", "key", "where", "from", "join"}


def _is_snake_case(name: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", name))


def _looks_plural(name: str) -> bool:
    if name.endswith("ies") or name.endswith("ses") or name.endswith("xes"):
        return True
    if name.endswith("s") and not name.endswith("ss") and not name.endswith("us") and not name.endswith("status"):
        return True
    return False


def lint_schema(schema: Schema) -> list[LintIssue]:
    issues: list[LintIssue] = []
    related = set()
    for rel in schema.relationships:
        related.add(rel.from_table.lower())
        related.add(rel.to_table.lower())

    indexed_cols: dict[str, set[str]] = {}
    for table in schema.tables:
        ic = set()
        for idx in table.indexes:
            ic.update(idx.columns)
        for col in table.columns:
            if col.primary_key:
                ic.add(col.name)
        indexed_cols[table.name] = ic

    for table in schema.tables:
        if not _is_snake_case(table.name):
            issues.append(LintIssue("ERD001", "warning", table.name, f"Table '{table.name}' not snake_case"))
        if _looks_plural(table.name):
            issues.append(LintIssue("ERD007", "info", table.name, f"Table '{table.name}' appears plural"))
        if table.name.lower() in SQL_KEYWORDS:
            issues.append(LintIssue("ERD008", "warning", table.name, f"Table '{table.name}' is SQL keyword"))
        if not table.primary_keys:
            issues.append(LintIssue("ERD004", "error", table.name, f"Table '{table.name}' has no PK"))
        if table.name.lower() not in related and len(schema.tables) > 1:
            issues.append(LintIssue("ERD006", "info", table.name, f"Table '{table.name}' is orphan"))
        for col in table.columns:
            if not _is_snake_case(col.name):
                issues.append(LintIssue("ERD002", "warning", table.name, f"Column '{table.name}.{col.name}' not snake_case"))
            if col.foreign_key and not col.name.endswith("_id"):
                issues.append(LintIssue("ERD003", "warning", table.name, f"FK '{table.name}.{col.name}' should end '_id'"))
            if col.foreign_key and col.name not in indexed_cols.get(table.name, set()):
                issues.append(LintIssue("ERD005", "warning", table.name, f"FK '{table.name}.{col.name}' not indexed"))
    return issues
