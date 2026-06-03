"""Policy loader — reads policy.yaml + column_policy.json for LLM prompts."""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from text2sql_agent.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_POLICY_PATH = Path(__file__).parent.parent.parent / "data" / "policy.yaml"
_DEFAULT_COLUMN_POLICY_PATH = Path(__file__).parent.parent.parent / "data" / "column_policy.json"


@lru_cache(maxsize=1)
def _load_policy(policy_path: str | None = None) -> dict[str, Any]:
    """Load and cache policy YAML file."""
    path = Path(policy_path) if policy_path else _DEFAULT_POLICY_PATH
    if not path.exists():
        logger.warning(f"Policy file not found: {path}")
        return {}

    with open(path) as f:
        policy = yaml.safe_load(f)

    logger.info(f"Loaded policy from {path}")
    return policy or {}


def get_policy() -> dict[str, Any]:
    """Get the cached policy dict."""
    return _load_policy()


@lru_cache(maxsize=1)
def _load_column_policy(policy_path: str | None = None) -> dict[str, Any]:
    """Load and cache column policy JSON file (same format as postgresql-mcp-server)."""
    path = Path(policy_path) if policy_path else _DEFAULT_COLUMN_POLICY_PATH
    if not path.exists():
        logger.warning(f"Column policy file not found: {path}")
        return {}

    with open(path) as f:
        policy = json.load(f)

    logger.info(f"Loaded column policy from {path} ({len(policy)} tables)")
    return policy or {}


def get_column_policy() -> dict[str, Any]:
    """Get the cached column policy dict."""
    return _load_column_policy()


def format_policy_context(candidate_tables: list[str] | None = None) -> str:
    """Format policy rules into a text context string for LLM prompts.

    Filters rules to only include tables relevant to candidate_tables
    if provided. Returns empty string if no policy loaded.
    """
    policy = get_policy()
    if not policy:
        return ""

    parts = []

    # Forbidden columns
    forbidden = policy.get("forbidden_columns", {})
    if forbidden:
        relevant = {}
        for table, cols in forbidden.items():
            if candidate_tables is None or table in candidate_tables:
                relevant[table] = cols
        if relevant:
            lines = ["FORBIDDEN COLUMNS (never SELECT these):"]
            for table, cols in relevant.items():
                lines.append(f"  {table}: {', '.join(cols)}")
            parts.append("\n".join(lines))

    # Sensitive tables requiring scope filter
    sensitive = policy.get("sensitive_tables", [])
    if sensitive:
        relevant = sensitive
        if candidate_tables:
            relevant = [t for t in sensitive if t in candidate_tables]
        if relevant:
            parts.append(
                "SENSITIVE TABLES (require customer/account filter in WHERE):\n"
                f"  {', '.join(relevant)}"
            )

    # Required time filters
    time_filters = policy.get("required_time_filters", {})
    if time_filters:
        relevant = {}
        for table, config in time_filters.items():
            if candidate_tables is None or table in candidate_tables:
                relevant[table] = config
        if relevant:
            lines = ["REQUIRED TIME FILTERS:"]
            for table, config in relevant.items():
                col = config["column"]
                days = config["max_range_days"]
                lines.append(f"  {table}.{col}: max {days} days lookback")
            parts.append("\n".join(lines))

    # Limits
    max_limit = policy.get("max_limit", 1000)
    default_limit = policy.get("default_limit", 100)
    parts.append(f"LIMITS: default={default_limit}, max={max_limit}")

    # Blocked patterns
    blocked = policy.get("blocked_patterns", [])
    if blocked:
        parts.append("BLOCKED PATTERNS:\n  " + "\n  ".join(blocked))

    # Aggregation caution
    agg_tables = policy.get("aggregation_caution_tables", [])
    if agg_tables:
        relevant = agg_tables
        if candidate_tables:
            relevant = [t for t in agg_tables if t in candidate_tables]
        if relevant:
            parts.append(
                "AGGREGATION CAUTION (check for double-counting with JOINs):\n"
                f"  {', '.join(relevant)}"
            )

    # Column policy from JSON (per-table allowed columns, required filters, etc.)
    column_policy = get_column_policy()
    if column_policy:
        col_lines = ["COLUMN POLICY (per-table access rules):"]
        for table_key, table_config in column_policy.items():
            # table_key is "public.table_name" — extract table name
            table_name = table_key.split(".", 1)[-1] if "." in table_key else table_key
            if candidate_tables and table_name not in candidate_tables:
                continue

            allowed = table_config.get("allowed_columns", [])
            required_filters = table_config.get("required_filter_columns", [])
            max_rows = table_config.get("max_rows")

            col_lines.append(f"\n  {table_name}:")
            col_lines.append(f"    allowed_columns: {', '.join(allowed)}")
            if required_filters:
                col_lines.append(f"    required_filter (WHERE must include): {', '.join(required_filters)}")
            if max_rows:
                col_lines.append(f"    max_rows: {max_rows}")

        if len(col_lines) > 1:
            parts.append("\n".join(col_lines))

    return "\n\n".join(parts)
