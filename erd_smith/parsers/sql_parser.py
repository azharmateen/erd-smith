"""Parse CREATE TABLE SQL statements into Schema objects.

Supports: tables, columns (name, type, nullable, default),
primary keys, foreign keys, unique constraints, indexes.
"""

from __future__ import annotations

import re

from .base import (
    BaseParser, Column, Index, Relationship, RelationType, Schema, Table,
)


# Common SQL type normalization
TYPE_MAP = {
    "int": "INTEGER",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "smallint": "SMALLINT",
    "tinyint": "SMALLINT",
    "serial": "SERIAL",
    "bigserial": "BIGSERIAL",
    "float": "FLOAT",
    "double": "DOUBLE",
    "real": "REAL",
    "decimal": "DECIMAL",
    "numeric": "NUMERIC",
    "varchar": "VARCHAR",
    "char": "CHAR",
    "text": "TEXT",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "date": "DATE",
    "time": "TIME",
    "timestamp": "TIMESTAMP",
    "timestamptz": "TIMESTAMPTZ",
    "datetime": "DATETIME",
    "json": "JSON",
    "jsonb": "JSONB",
    "uuid": "UUID",
    "blob": "BLOB",
    "bytea": "BYTEA",
}


def _normalize_type(raw_type: str) -> str:
    """Normalize SQL type string."""
    base = raw_type.strip().split("(")[0].lower()
    normalized = TYPE_MAP.get(base, raw_type.upper())
    # Preserve length/precision info
    paren_match = re.search(r"\(([^)]+)\)", raw_type)
    if paren_match:
        return f"{normalized}({paren_match.group(1)})"
    return normalized


def _strip_comments(sql: str) -> str:
    """Remove SQL comments."""
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


class SqlParser(BaseParser):

    def can_parse(self, source: str) -> bool:
        return bool(re.search(r"CREATE\s+TABLE", source, re.IGNORECASE))

    def parse(self, source: str) -> Schema:
        source = _strip_comments(source)
        schema = Schema()

        # Extract CREATE TABLE statements
        pattern = re.compile(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w+)[`\"\]]?\s*\((.*?)\)\s*;",
            re.IGNORECASE | re.DOTALL,
        )

        for match in pattern.finditer(source):
            table_name = match.group(1)
            body = match.group(2)
            table = self._parse_table_body(table_name, body)
            schema.tables.append(table)

        # Build relationships from foreign keys
        for table in schema.tables:
            for col in table.foreign_keys:
                if col.foreign_key:
                    parts = col.foreign_key.split(".")
                    if len(parts) == 2:
                        schema.relationships.append(Relationship(
                            from_table=table.name,
                            from_column=col.name,
                            to_table=parts[0],
                            to_column=parts[1],
                            relation_type=RelationType.ONE_TO_MANY,
                        ))

        # Parse standalone CREATE INDEX
        idx_pattern = re.compile(
            r"CREATE\s+(?:(UNIQUE)\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w+)[`\"\]]?\s+"
            r"ON\s+[`\"\[]?(\w+)[`\"\]]?\s*\(([^)]+)\)",
            re.IGNORECASE,
        )
        for match in idx_pattern.finditer(source):
            unique = match.group(1) is not None
            idx_name = match.group(2)
            tbl_name = match.group(3)
            cols = [c.strip().strip("`\"[]") for c in match.group(4).split(",")]

            table = schema.get_table(tbl_name)
            if table:
                table.indexes.append(Index(name=idx_name, columns=cols, unique=unique))

        return schema

    def _parse_table_body(self, table_name: str, body: str) -> Table:
        """Parse the body of a CREATE TABLE statement."""
        table = Table(name=table_name)

        # Split by commas, but respect parentheses
        parts = self._split_definitions(body)

        composite_pk: list[str] = []

        for part in parts:
            part = part.strip()
            if not part:
                continue

            upper = part.upper().lstrip()

            # Table-level PRIMARY KEY
            pk_match = re.match(
                r"PRIMARY\s+KEY\s*\(([^)]+)\)", part, re.IGNORECASE
            )
            if pk_match:
                composite_pk = [c.strip().strip("`\"[]") for c in pk_match.group(1).split(",")]
                continue

            # Table-level UNIQUE
            uniq_match = re.match(
                r"(?:CONSTRAINT\s+\w+\s+)?UNIQUE\s*\(([^)]+)\)", part, re.IGNORECASE
            )
            if uniq_match:
                cols = [c.strip().strip("`\"[]") for c in uniq_match.group(1).split(",")]
                table.indexes.append(Index(name=f"uq_{table_name}_{'_'.join(cols)}", columns=cols, unique=True))
                continue

            # Table-level FOREIGN KEY
            fk_match = re.match(
                r"(?:CONSTRAINT\s+\w+\s+)?FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+[`\"\[]?(\w+)[`\"\]]?\s*\(([^)]+)\)",
                part, re.IGNORECASE,
            )
            if fk_match:
                local_cols = [c.strip().strip("`\"[]") for c in fk_match.group(1).split(",")]
                ref_table = fk_match.group(2)
                ref_cols = [c.strip().strip("`\"[]") for c in fk_match.group(3).split(",")]
                for lc, rc in zip(local_cols, ref_cols):
                    for col in table.columns:
                        if col.name == lc:
                            col.foreign_key = f"{ref_table}.{rc}"
                continue

            # Table-level CHECK/CONSTRAINT (skip)
            if upper.startswith("CHECK") or upper.startswith("CONSTRAINT"):
                continue

            # Column definition
            col = self._parse_column(part)
            if col:
                table.columns.append(col)

        # Apply composite PK
        for pk_col in composite_pk:
            for col in table.columns:
                if col.name == pk_col:
                    col.primary_key = True

        return table

    def _parse_column(self, definition: str) -> Column | None:
        """Parse a single column definition."""
        # Match: column_name TYPE [(size)] [constraints...]
        match = re.match(
            r"[`\"\[]?(\w+)[`\"\]]?\s+(\w+(?:\s*\([^)]*\))?)\s*(.*)",
            definition.strip(),
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        name = match.group(1)
        raw_type = match.group(2)
        constraints = match.group(3).upper()

        # Skip if it's a keyword not a column name
        if name.upper() in ("PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT", "INDEX", "KEY"):
            return None

        col = Column(
            name=name,
            data_type=_normalize_type(raw_type),
            nullable="NOT NULL" not in constraints,
            primary_key="PRIMARY KEY" in constraints or "PRIMARY" in constraints.split(),
            unique="UNIQUE" in constraints,
        )

        # Default value
        default_match = re.search(r"DEFAULT\s+(.+?)(?:\s+|$)", constraints, re.IGNORECASE)
        if default_match:
            col.default = default_match.group(1).strip().rstrip(",")

        # Inline REFERENCES
        ref_match = re.search(
            r"REFERENCES\s+[`\"\[]?(\w+)[`\"\]]?\s*\(([^)]+)\)",
            match.group(3), re.IGNORECASE,
        )
        if ref_match:
            ref_table = ref_match.group(1)
            ref_col = ref_match.group(2).strip().strip("`\"[]")
            col.foreign_key = f"{ref_table}.{ref_col}"

        # Auto-increment implies PK
        if "AUTOINCREMENT" in constraints or "AUTO_INCREMENT" in constraints:
            col.primary_key = True

        # SERIAL types are PK
        if raw_type.lower() in ("serial", "bigserial"):
            col.primary_key = True
            col.nullable = False

        return col

    def _split_definitions(self, body: str) -> list[str]:
        """Split column/constraint definitions by comma, respecting parentheses."""
        parts = []
        depth = 0
        current = []

        for char in body:
            if char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth -= 1
                current.append(char)
            elif char == "," and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(char)

        if current:
            parts.append("".join(current))

        return parts
