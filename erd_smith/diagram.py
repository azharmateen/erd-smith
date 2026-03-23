"""ERD generator: create Mermaid, PlantUML, DOT diagram syntax from parsed schema."""

from __future__ import annotations

from .parser import Schema


def _mermaid_type(col_type: str) -> str:
    return col_type.replace("(", "_").replace(")", "").replace(",", "_")


def to_mermaid(schema: Schema) -> str:
    lines: list[str] = ["erDiagram"]
    for table in schema.tables:
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            flags = []
            if col.primary_key:
                flags.append("PK")
            if col.references:
                flags.append("FK")
            if col.unique and not col.primary_key:
                flags.append("UK")
            flag_str = " ".join(flags)
            clean_type = _mermaid_type(col.data_type)
            if flag_str:
                lines.append(f"        {clean_type} {col.name} {flag_str}")
            else:
                lines.append(f"        {clean_type} {col.name}")
        lines.append("    }")
    for table in schema.tables:
        for fk in table.foreign_keys:
            fk_col = table.get_column(fk.columns[0]) if fk.columns else None
            is_unique = fk_col.unique if fk_col else False
            rel = "||--||" if is_unique else "||--o{"
            label = ",".join(fk.columns)
            lines.append(f"    {fk.ref_table} {rel} {table.name} : \"{label}\"")
    return "\n".join(lines)


def to_plantuml(schema: Schema) -> str:
    lines: list[str] = ["@startuml", "skinparam linetype ortho", ""]
    for table in schema.tables:
        lines.append(f"entity {table.name} {{")
        pk_cols = [c for c in table.columns if c.primary_key]
        other_cols = [c for c in table.columns if not c.primary_key]
        for col in pk_cols:
            lines.append(f"    * {col.name} : {col.data_type} <<PK>>")
        if pk_cols and other_cols:
            lines.append("    --")
        for col in other_cols:
            nullable = "" if col.nullable else " NOT NULL"
            fk_tag = " <<FK>>" if col.references else ""
            lines.append(f"    {col.name} : {col.data_type}{nullable}{fk_tag}")
        lines.append("}")
        lines.append("")
    for table in schema.tables:
        for fk in table.foreign_keys:
            fk_col = table.get_column(fk.columns[0]) if fk.columns else None
            rel = "||--||" if (fk_col and fk_col.unique) else "||--o{"
            lines.append(f"{fk.ref_table} {rel} {table.name}")
    lines.extend(["", "@enduml"])
    return "\n".join(lines)


def to_dot(schema: Schema) -> str:
    lines: list[str] = [
        "digraph ERD {",
        "    graph [rankdir=LR, fontname=\"Helvetica\", fontsize=12];",
        "    node [shape=record, fontname=\"Helvetica\", fontsize=10];",
        "    edge [fontname=\"Helvetica\", fontsize=9];",
        "",
    ]
    for table in schema.tables:
        col_rows: list[str] = []
        for col in table.columns:
            flags = ""
            if col.primary_key:
                flags += " [PK]"
            if col.references:
                flags += " [FK]"
            col_rows.append(f"{col.name} : {col.data_type}{flags}")
        col_label = "\\l".join(col_rows) + "\\l"
        label = f"{{{table.name}|{col_label}}}"
        lines.append(f"    {table.name} [label=\"{label}\"];")
    lines.append("")
    for table in schema.tables:
        for fk in table.foreign_keys:
            label = ",".join(fk.columns)
            fk_col = table.get_column(fk.columns[0]) if fk.columns else None
            head = "crowodot" if not (fk_col and fk_col.unique) else "teetee"
            lines.append(f"    {fk.ref_table} -> {table.name} [label=\"{label}\", arrowhead={head}];")
    lines.append("}")
    return "\n".join(lines)


def generate_diagram(schema: Schema, fmt: str = "mermaid") -> str:
    if fmt == "mermaid":
        return to_mermaid(schema)
    elif fmt == "plantuml":
        return to_plantuml(schema)
    elif fmt == "dot":
        return to_dot(schema)
    else:
        raise ValueError(f"Unknown format: {fmt}")
