"""Base parser interface for all schema formats."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class RelationType(str, Enum):
    ONE_TO_ONE = "one-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_MANY = "many-to-many"


@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    default: str | None = None
    foreign_key: str | None = None  # "table.column" format

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "type": self.data_type,
            "nullable": self.nullable,
        }
        if self.primary_key:
            d["primary_key"] = True
        if self.unique:
            d["unique"] = True
        if self.default is not None:
            d["default"] = self.default
        if self.foreign_key:
            d["foreign_key"] = self.foreign_key
        return d


@dataclass
class Index:
    name: str
    columns: list[str]
    unique: bool = False


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)

    @property
    def primary_keys(self) -> list[Column]:
        return [c for c in self.columns if c.primary_key]

    @property
    def foreign_keys(self) -> list[Column]:
        return [c for c in self.columns if c.foreign_key]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "columns": [c.to_dict() for c in self.columns],
            "indexes": [
                {"name": i.name, "columns": i.columns, "unique": i.unique}
                for i in self.indexes
            ],
        }


@dataclass
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relation_type: RelationType = RelationType.ONE_TO_MANY

    def to_dict(self) -> dict:
        return {
            "from": f"{self.from_table}.{self.from_column}",
            "to": f"{self.to_table}.{self.to_column}",
            "type": self.relation_type.value,
        }


@dataclass
class Schema:
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    def get_table(self, name: str) -> Table | None:
        for t in self.tables:
            if t.name.lower() == name.lower():
                return t
        return None

    @property
    def table_names(self) -> list[str]:
        return [t.name for t in self.tables]

    def to_dict(self) -> dict:
        return {
            "tables": [t.to_dict() for t in self.tables],
            "relationships": [r.to_dict() for r in self.relationships],
        }


class BaseParser(ABC):
    """Abstract base class for schema parsers."""

    @abstractmethod
    def parse(self, source: str) -> Schema:
        """Parse source text into a Schema."""
        ...

    @abstractmethod
    def can_parse(self, source: str) -> bool:
        """Check if this parser can handle the given source."""
        ...
