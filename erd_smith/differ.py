"""Schema diff: compare two schemas."""

from __future__ import annotations

from dataclasses import dataclass, field

from .parser import Schema, Table


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

    def to_markdown(self) -> str:
        lines: list[str] = ["# Schema Diff", ""]
        if self.added_tables:
            lines.append("## Added Tables")
            for t in self.added_tables:
                lines.append(f"- `{t}`")
            lines.append("")
        if self.removed_tables:
            lines.append("## Removed Tables")
            for t in self.removed_tables:
                lines.append(f"- `{t}`")
            lines.append("")
        if self.modified_tables:
            lines.append("## Modified Tables")
            for td in self.modified_tables:
                lines.append(f"\n### {td.table_name}")
                for col in td.added_columns:
                    lines.append(f"- Added: `{col}`")
                for col in td.removed_columns:
                    lines.append(f"- Removed: `{col}`")
                for cd in td.modified_columns:
                    lines.append(f"- Changed `{cd.name}` ({cd.change}): `{cd.old_value}` -> `{cd.new_value}`")
            lines.append("")
        if not self.has_changes:
            lines.append("No changes detected.")
        return "\n".join(lines)


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
            old_c = old_cols[name]
            new_c = new_cols[name]
            if old_c.data_type.upper() != new_c.data_type.upper():
                td.modified_columns.append(ColumnDiff(name=new_c.name, change="type_changed",
                                                      old_value=old_c.data_type, new_value=new_c.data_type))
            if old_c.nullable != new_c.nullable:
                td.modified_columns.append(ColumnDiff(name=new_c.name, change="nullable_changed",
                                                      old_value="nullable" if old_c.nullable else "not null",
                                                      new_value="nullable" if new_c.nullable else "not null"))
            if (old_c.references or "") != (new_c.references or ""):
                td.modified_columns.append(ColumnDiff(name=new_c.name, change="fk_changed",
                                                      old_value=old_c.references or "(none)",
                                                      new_value=new_c.references or "(none)"))
    return td


def diff_schemas(old: Schema, new: Schema) -> SchemaDiff:
    result = SchemaDiff()
    old_tables = {t.name.lower(): t for t in old.tables}
    new_tables = {t.name.lower(): t for t in new.tables}
    for name in new_tables:
        if name not in old_tables:
            result.added_tables.append(new_tables[name].name)
    for name in old_tables:
        if name not in new_tables:
            result.removed_tables.append(old_tables[name].name)
    for name in old_tables:
        if name in new_tables:
            td = _diff_tables(old_tables[name], new_tables[name])
            if td.added_columns or td.removed_columns or td.modified_columns:
                result.modified_tables.append(td)
    return result
