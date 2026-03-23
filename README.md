# erd-smith

Auto-generate database ERD diagrams from SQL, Django, or SQLAlchemy schemas.

## Features

- **Parse SQL** CREATE TABLE statements (PostgreSQL, MySQL, SQLite)
- **Parse Django** models.py with ForeignKey/M2M relationship detection
- **4 output formats**: Mermaid, Graphviz DOT, ASCII art, DBML
- **Schema diff**: compare two schemas and detect changes
- **Schema lint**: naming conventions, missing indexes, orphan tables
- **Auto-detect** schema format or force with `--orm`

## Install

```bash
pip install -e .
```

## Usage

```bash
# Generate Mermaid ERD from SQL
erd-smith generate schema.sql

# Generate from Django models
erd-smith generate models.py --orm django

# Output as Graphviz DOT
erd-smith generate schema.sql --format dot -o erd.dot

# ASCII art (no external tools needed)
erd-smith generate schema.sql --format ascii

# Compare two schemas
erd-smith diff old_schema.sql new_schema.sql

# Lint schema for best practices
erd-smith lint schema.sql
```

## Output Formats

| Format | Use Case |
|--------|----------|
| `mermaid` | Embed in Markdown, GitHub renders natively |
| `dot` | Render with Graphviz (`dot -Tpng erd.dot -o erd.png`) |
| `ascii` | Terminal viewing, no dependencies |
| `dbml` | Import into dbdiagram.io |
| `json` | Programmatic consumption |

## Lint Rules

| Rule | Level | Description |
|------|-------|-------------|
| ERD001 | warning | Table name should be snake_case |
| ERD002 | warning | Column name should be snake_case |
| ERD003 | warning | FK column should end with _id |
| ERD004 | error | Table must have a primary key |
| ERD005 | warning | FK columns should be indexed |
| ERD006 | info | Orphan table (no relationships) |
| ERD007 | info | Table name should be singular |
| ERD008 | warning | Avoid SQL reserved keywords |

## License

MIT
