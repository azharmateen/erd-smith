"""Schema diff: compare two schemas, detect added/removed tables, column changes."""

from __future__ import annotations

from dataclasses import dataclass, field

from .parsers.base import Schema, Table, Column


@dataclass
class ColumnDiff:
    name: str
    change: str
    old_value: str = ""
    new_value: str = ""


@dataclass
class TableDiff:
    table_name: str
    added_columns: list[str] = field(default_factory=list)
    removed_columns: list[str] = field(default_factory=list)
    modified_columns: list[ColumnDiff] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "table": self.table_name,
            "added_columns": self.added_columns,
            "removed_columns": self.removed_columns,
            "modified_columns": [
                {"name": c.name, "change": c.change, "old": c.old_value, "new": c.new_value}
                for c in self.modified_columns
            ],
        }


@dataclass
class SchemaDiff:
    added_tables: list[str] = field(default_factory=list)
    removed_tables: list[str] = field(default_factory=list)
    modified_tables: list[TableDiff] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added_tables or self.removed_tables or self.modified_tables)

    def to_dict(self) -> dict:
        return {
            "added_tables": self.added_tables,
            "removed_tables": self.removed_tables,
            "modified_tables": [t.to_dict() for t in self.modified_tables],
        }

    def summary(self) -> str:
        parts = []
        if self.added_tables:
            parts.append(f"+{len(self.added_tables)} tables")
        if self.removed_tables:
            parts.append(f"-{len(self.removed_tables)} tables")
        if self.modified_tables:
            parts.append(f"~{len(self.modified_tables)} modified")
        return ", ".join(parts) if parts else "no changes"


def diff_schemas(old: Schema, new: Schema) -> SchemaDiff:
    result = SchemaDiff()
    old_names = {t.name.lower(): t for t in old.tables}
    new_names = {t.name.lower(): t for t in new.tables}

    for name in new_names:
        if name not in old_names:
            result.added_tables.append(new_names[name].name)
    for name in old_names:
        if name not in new_names:
            result.removed_tables.append(old_names[name].name)
    for name in old_names:
        if name in new_names:
            td = _diff_tables(old_names[name], new_names[name])
            if td.added_columns or td.removed_columns or td.modified_columns:
                result.modified_tables.append(td)
    return result


def _diff_tables(old: Table, new: Table) -> TableDiff:
    td = TableDiff(table_name=new.name)
    old_cols = {c.name.lower(): c for c in old.columns}
    new_cols = {c.name.lower(): c for c in new.columns}

    for name in new_cols:
        if name not in old_cols:
            td.added_columns.append(new_cols[name].name)
    for name in old_cols:
        if name not in new_cols:
            td.removed_columns.append(old_cols[name].name)
    for name in old_cols:
        if name in new_cols:
            oc, nc = old_cols[name], new_cols[name]
            if oc.data_type != nc.data_type:
                td.modified_columns.append(ColumnDiff(nc.name, "type_changed", oc.data_type, nc.data_type))
            if oc.nullable != nc.nullable:
                td.modified_columns.append(ColumnDiff(nc.name, "nullable_changed",
                    "nullable" if oc.nullable else "not null", "nullable" if nc.nullable else "not null"))
            if oc.foreign_key != nc.foreign_key:
                td.modified_columns.append(ColumnDiff(nc.name, "fk_changed",
                    oc.foreign_key or "(none)", nc.foreign_key or "(none)"))
    return td
