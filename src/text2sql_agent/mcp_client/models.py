"""Typed output models for MCP client responses.

Agent nodes use these instead of raw dicts, ensuring consistency
across all MCP client implementations.
"""

from pydantic import BaseModel


class ColumnInfo(BaseModel):
    """Column definition from get_table_schema."""

    ordinal_position: int
    column_name: str
    data_type: str
    is_nullable: bool
    column_default: str | None = None


class TableSchema(BaseModel):
    """Structured result from get_table_schema."""

    schema_name: str
    table: str
    columns: list[ColumnInfo]


class Constraint(BaseModel):
    """Constraint definition from get_constraints."""

    constraint_name: str
    constraint_type_name: str
    columns: list[str]
    foreign_schema: str | None = None
    foreign_table: str | None = None
    foreign_columns: list[str] = []


class Index(BaseModel):
    """Index definition from get_indexes."""

    index_name: str
    is_primary: bool
    is_unique: bool
    index_type: str | None = None
    columns: list[str]


class DryRunResult(BaseModel):
    """Result from dry_run_query."""

    valid: bool
    message: str
    error: str | None = None
