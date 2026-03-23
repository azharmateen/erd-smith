"""Parse Django models.py files into Schema objects via regex.

Extracts model classes, fields, ForeignKey/OneToOneField/ManyToManyField.
"""

from __future__ import annotations

import re

from .base import (
    BaseParser, Column, Relationship, RelationType, Schema, Table,
)


# Django field type to SQL type mapping
DJANGO_TYPE_MAP = {
    "AutoField": "INTEGER",
    "BigAutoField": "BIGINT",
    "SmallAutoField": "SMALLINT",
    "CharField": "VARCHAR",
    "TextField": "TEXT",
    "IntegerField": "INTEGER",
    "BigIntegerField": "BIGINT",
    "SmallIntegerField": "SMALLINT",
    "PositiveIntegerField": "INTEGER",
    "PositiveBigIntegerField": "BIGINT",
    "PositiveSmallIntegerField": "SMALLINT",
    "FloatField": "FLOAT",
    "DecimalField": "DECIMAL",
    "BooleanField": "BOOLEAN",
    "NullBooleanField": "BOOLEAN",
    "DateField": "DATE",
    "DateTimeField": "DATETIME",
    "TimeField": "TIME",
    "DurationField": "INTERVAL",
    "EmailField": "VARCHAR(254)",
    "URLField": "VARCHAR(200)",
    "UUIDField": "UUID",
    "SlugField": "VARCHAR(50)",
    "IPAddressField": "VARCHAR(15)",
    "GenericIPAddressField": "VARCHAR(39)",
    "FileField": "VARCHAR(100)",
    "ImageField": "VARCHAR(100)",
    "BinaryField": "BLOB",
    "JSONField": "JSON",
    "ForeignKey": "INTEGER",
    "OneToOneField": "INTEGER",
    "ManyToManyField": None,  # Junction table, not a column
}


def _model_name_to_table(name: str) -> str:
    """Convert CamelCase model name to snake_case table name."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


def _extract_string_arg(args: str, position: int = 0) -> str | None:
    """Extract a positional string argument from field args."""
    # Match quoted strings
    strings = re.findall(r"""['"]([^'"]+)['"]""", args)
    if position < len(strings):
        return strings[position]
    return None


def _extract_kwarg(args: str, key: str) -> str | None:
    """Extract a keyword argument value."""
    match = re.search(rf"{key}\s*=\s*([^,\)]+)", args)
    if match:
        val = match.group(1).strip().strip("'\"")
        return val
    return None


class DjangoParser(BaseParser):

    def can_parse(self, source: str) -> bool:
        return bool(re.search(r"class\s+\w+\(.*models\.Model.*\)", source))

    def parse(self, source: str) -> Schema:
        schema = Schema()
        m2m_relations: list[tuple[str, str, str]] = []  # (from_model, to_model, field_name)

        # Find all model classes
        model_pattern = re.compile(
            r"^class\s+(\w+)\s*\(.*?models\.Model.*?\)\s*:",
            re.MULTILINE,
        )

        model_starts = [(m.start(), m.group(1)) for m in model_pattern.finditer(source)]

        for i, (start, model_name) in enumerate(model_starts):
            end = model_starts[i + 1][0] if i + 1 < len(model_starts) else len(source)
            model_body = source[start:end]

            table_name = _model_name_to_table(model_name)
            table = Table(name=table_name)

            # Add implicit PK if not overridden
            has_explicit_pk = bool(re.search(r"primary_key\s*=\s*True", model_body))
            has_auto_field = bool(re.search(r"(?:Auto|Big(?:Auto)?)Field", model_body))

            if not has_explicit_pk and not has_auto_field:
                table.columns.append(Column(
                    name="id",
                    data_type="BIGINT",
                    nullable=False,
                    primary_key=True,
                ))

            # Parse field definitions
            field_pattern = re.compile(
                r"^\s+(\w+)\s*=\s*models\.(\w+)\(([^)]*(?:\([^)]*\))*[^)]*)\)",
                re.MULTILINE,
            )

            for field_match in field_pattern.finditer(model_body):
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                field_args = field_match.group(3)

                if field_type == "ManyToManyField":
                    target = _extract_string_arg(field_args)
                    if target:
                        target_table = _model_name_to_table(target)
                        m2m_relations.append((table_name, target_table, field_name))
                    continue

                sql_type = DJANGO_TYPE_MAP.get(field_type, "TEXT")

                # Extract max_length for CharField
                if field_type in ("CharField", "SlugField", "URLField", "EmailField"):
                    max_len = _extract_kwarg(field_args, "max_length")
                    if max_len:
                        sql_type = f"VARCHAR({max_len})"

                nullable = False
                if _extract_kwarg(field_args, "null") in ("True", "true"):
                    nullable = True

                is_pk = _extract_kwarg(field_args, "primary_key") in ("True", "true")
                is_unique = _extract_kwarg(field_args, "unique") in ("True", "true")

                default = _extract_kwarg(field_args, "default")

                col = Column(
                    name=field_name if field_type not in ("ForeignKey", "OneToOneField") else f"{field_name}_id",
                    data_type=sql_type,
                    nullable=nullable,
                    primary_key=is_pk,
                    unique=is_unique or field_type == "OneToOneField",
                    default=default,
                )

                # FK reference
                if field_type in ("ForeignKey", "OneToOneField"):
                    target = _extract_string_arg(field_args)
                    if not target:
                        # Try unquoted reference
                        first_arg = field_args.split(",")[0].strip()
                        if first_arg and not first_arg.startswith(("'", '"')):
                            target = first_arg

                    if target:
                        if target == "self":
                            target_table = table_name
                        else:
                            target_table = _model_name_to_table(target)
                        col.foreign_key = f"{target_table}.id"

                        rel_type = RelationType.ONE_TO_ONE if field_type == "OneToOneField" else RelationType.ONE_TO_MANY
                        schema.relationships.append(Relationship(
                            from_table=table_name,
                            from_column=col.name,
                            to_table=target_table,
                            to_column="id",
                            relation_type=rel_type,
                        ))

                table.columns.append(col)

            schema.tables.append(table)

        # Create junction tables for M2M
        for from_table, to_table, field_name in m2m_relations:
            jt_name = f"{from_table}_{field_name}"
            jt = Table(name=jt_name, columns=[
                Column(name="id", data_type="BIGINT", nullable=False, primary_key=True),
                Column(name=f"{from_table}_id", data_type="BIGINT", nullable=False,
                       foreign_key=f"{from_table}.id"),
                Column(name=f"{to_table}_id", data_type="BIGINT", nullable=False,
                       foreign_key=f"{to_table}.id"),
            ])
            schema.tables.append(jt)
            schema.relationships.append(Relationship(
                from_table=jt_name, from_column=f"{from_table}_id",
                to_table=from_table, to_column="id",
                relation_type=RelationType.ONE_TO_MANY,
            ))
            schema.relationships.append(Relationship(
                from_table=jt_name, from_column=f"{to_table}_id",
                to_table=to_table, to_column="id",
                relation_type=RelationType.ONE_TO_MANY,
            ))

        return schema
