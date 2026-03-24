"""Generate ERD diagrams: Mermaid erDiagram, DOT/Graphviz, ASCII art, DBML."""

from __future__ import annotations

from .parsers.base import Column, RelationType, Schema


def _mermaid_type(col: Column) -> str:
    t = col.data_type.split("(")[0]
    return t.lower()


def _mermaid_rel_symbol(rel_type: RelationType) -> str:
    return {
        RelationType.ONE_TO_ONE: "||--||",
        RelationType.ONE_TO_MANY: "||--o{",
        RelationType.MANY_TO_MANY: "}o--o{",
    }[rel_type]


def to_mermaid(schema: Schema) -> str:
    lines = ["erDiagram"]
    for table in schema.tables:
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            markers = []
            if col.primary_key:
                markers.append("PK")
            if col.foreign_key:
                markers.append("FK")
            if col.unique and not col.primary_key:
                markers.append("UK")
            marker_str = f' "{",".join(markers)}"' if markers else ""
            lines.append(f"        {_mermaid_type(col)} {col.name}{marker_str}")
        lines.append("    }")
    for rel in schema.relationships:
        symbol = _mermaid_rel_symbol(rel.relation_type)
        label = f"{rel.from_column} -> {rel.to_column}"
        lines.append(f"    {rel.from_table} {symbol} {rel.to_table} : \"{label}\"")
    return "\n".join(lines)


def to_dot(schema: Schema) -> str:
    lines = [
        "digraph ERD {",
        '    graph [rankdir=LR, fontname="Helvetica", bgcolor="white"];',
        '    node [shape=plaintext, fontname="Helvetica"];',
        '    edge [fontname="Helvetica", fontsize=10];',
        "",
    ]
    for table in schema.tables:
        rows = []
        for col in table.columns:
            markers = []
            if col.primary_key:
                markers.append("PK")
            if col.foreign_key:
                markers.append("FK")
            marker = f'<font color="gray"> [{",".join(markers)}]</font>' if markers else ""
            null_str = "" if col.nullable else " NOT NULL"
            rows.append(
                f'<tr><td align="left" port="{col.name}">'
                f'<b>{col.name}</b></td>'
                f'<td align="left">{col.data_type}{null_str}</td>'
                f'<td align="left">{marker}</td></tr>'
            )
        rows_str = "\n".join(rows)
        label = (
            f'<<table border="1" cellborder="0" cellspacing="0" cellpadding="4">'
            f'<tr><td colspan="3" bgcolor="#4a90d9"><font color="white"><b>{table.name}</b></font></td></tr>'
            f'{rows_str}'
            f'</table>>'
        )
        lines.append(f'    {table.name} [label={label}];')
    lines.append("")
    for rel in schema.relationships:
        arrow = "normal"
        if rel.relation_type == RelationType.ONE_TO_ONE:
            arrow = "tee"
        elif rel.relation_type == RelationType.MANY_TO_MANY:
            arrow = "crow"
        lines.append(
            f'    {rel.from_table}:{rel.from_column} -> {rel.to_table}:{rel.to_column} '
            f'[arrowhead={arrow}, label="{rel.relation_type.value}"];'
        )
    lines.append("}")
    return "\n".join(lines)


def to_ascii(schema: Schema) -> str:
    lines = []
    for table in schema.tables:
        name_width = max((len(col.name) for col in table.columns), default=4)
        type_width = max((len(col.data_type) for col in table.columns), default=4)
        name_width = max(name_width, len(table.name) - 3)
        type_width = max(type_width, 4)
        total_width = name_width + type_width + 12
        lines.append("+" + "-" * total_width + "+")
        header = f"| {table.name:^{total_width - 2}} |"
        lines.append(header)
        lines.append("+" + "=" * total_width + "+")
        for col in table.columns:
            flags = []
            if col.primary_key:
                flags.append("PK")
            if col.foreign_key:
                flags.append("FK")
            if col.unique and not col.primary_key:
                flags.append("UK")
            flag_str = ",".join(flags)
            null_str = "" if col.nullable else "*"
            col_line = f"| {null_str}{col.name:<{name_width}} | {col.data_type:<{type_width}} | {flag_str:<4} |"
            lines.append(col_line)
        lines.append("+" + "-" * total_width + "+")
        lines.append("")
    if schema.relationships:
        lines.append("Relationships:")
        for rel in schema.relationships:
            arrow = {
                RelationType.ONE_TO_ONE: "1--1",
                RelationType.ONE_TO_MANY: "1--*",
                RelationType.MANY_TO_MANY: "*--*",
            }[rel.relation_type]
            lines.append(f"  {rel.from_table}.{rel.from_column} {arrow} {rel.to_table}.{rel.to_column}")
    return "\n".join(lines)


def to_dbml(schema: Schema) -> str:
    lines = []
    for table in schema.tables:
        lines.append(f"Table {table.name} {{")
        for col in table.columns:
            settings = []
            if col.primary_key:
                settings.append("pk")
            if not col.nullable:
                settings.append("not null")
            if col.unique and not col.primary_key:
                settings.append("unique")
            if col.default:
                settings.append(f"default: {col.default}")
            settings_str = f" [{', '.join(settings)}]" if settings else ""
            lines.append(f"  {col.name} {col.data_type}{settings_str}")
        lines.append("}")
        lines.append("")
    for rel in schema.relationships:
        symbol = {
            RelationType.ONE_TO_ONE: "-",
            RelationType.ONE_TO_MANY: "<",
            RelationType.MANY_TO_MANY: "<>",
        }[rel.relation_type]
        lines.append(f"Ref: {rel.from_table}.{rel.from_column} {symbol} {rel.to_table}.{rel.to_column}")
    return "\n".join(lines)
