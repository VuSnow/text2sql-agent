"""Seed script: reads markdown docs and examples → embeds → upserts into ChromaDB.

Usage:
    python -m text2sql_agent.rag.seed
"""

import hashlib
import logging
import re
import sys
from pathlib import Path

from text2sql_agent.config import settings
from text2sql_agent.rag.store import RAGStore

logger = logging.getLogger(__name__)

DOCS_DIR = Path("data/docs")
EXAMPLES_DIR = Path("data/examples")


def parse_table_doc(filepath: Path) -> dict:
    """Parse a table description markdown file."""
    content = filepath.read_text(encoding="utf-8")
    table_name = filepath.stem  # e.g. "customers"

    # Extract first paragraph after "## 1. Mục đích bảng" as description
    desc_match = re.search(
        r"## 1\. Mục đích bảng\s*\n\n(.+?)(?:\n\n|\n##)",
        content,
        re.DOTALL,
    )
    description = desc_match.group(1).strip() if desc_match else ""

    return {
        "table_name": table_name,
        "description": description,
        "full_text": content,
    }


def parse_example(filepath: Path) -> dict | None:
    """Parse an example markdown file into structured data."""
    content = filepath.read_text(encoding="utf-8")

    # Title
    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filepath.stem

    # Complexity
    complexity_match = re.search(r"## Complexity:\s*(\w+)", content)
    complexity = complexity_match.group(1).strip() if complexity_match else "medium"

    # Tables Used
    tables_match = re.search(r"## Tables Used:\s*(.+)$", content, re.MULTILINE)
    tables = []
    if tables_match:
        tables = [t.strip() for t in tables_match.group(1).split(",")]

    # Question
    question_match = re.search(
        r"## Question \(Vietnamese\)\s*\n(.+?)(?:\n##)",
        content,
        re.DOTALL,
    )
    question = question_match.group(1).strip() if question_match else ""

    # SQL
    sql_match = re.search(r"```sql\s*\n(.+?)```", content, re.DOTALL)
    sql = sql_match.group(1).strip() if sql_match else ""

    # Explanation
    explanation_match = re.search(
        r"## Explanation\s*\n(.+?)(?:\n##|$)",
        content,
        re.DOTALL,
    )
    explanation = explanation_match.group(1).strip() if explanation_match else ""

    if not question or not sql:
        logger.warning(f"Skipping {filepath.name}: missing question or SQL")
        return None

    return {
        "example_id": hashlib.md5(question.encode()).hexdigest(),
        "title": title,
        "question": question,
        "sql": sql,
        "tables": tables,
        "complexity": complexity,
        "explanation": explanation,
        "full_text": content,
    }


def seed_schemas(store: RAGStore) -> int:
    """Seed schema_descriptions collection from data/docs/*.md."""
    docs_path = DOCS_DIR
    if not docs_path.exists():
        logger.error(f"Docs directory not found: {docs_path}")
        return 0

    md_files = sorted(docs_path.glob("*.md"))
    count = 0

    for filepath in md_files:
        doc = parse_table_doc(filepath)
        logger.info(f"  Upserting schema: {doc['table_name']}")
        store.upsert_schema(
            table_name=doc["table_name"],
            description=doc["description"],
            full_text=doc["full_text"],
        )
        count += 1

    return count


def seed_examples(store: RAGStore) -> int:
    """Seed sql_examples collection from data/examples/*.md."""
    examples_path = EXAMPLES_DIR
    if not examples_path.exists():
        logger.error(f"Examples directory not found: {examples_path}")
        return 0

    md_files = sorted(examples_path.glob("*.md"))
    count = 0

    for filepath in md_files:
        example = parse_example(filepath)
        if example is None:
            continue

        logger.info(f"  Upserting example: {filepath.name}")
        store.upsert_example(
            example_id=example["example_id"],
            question=example["question"],
            sql=example["sql"],
            tables=example["tables"],
            complexity=example["complexity"],
            explanation=example["explanation"],
            full_text=example["full_text"],
        )
        count += 1

    return count


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Initializing RAG store...")
    store = RAGStore()

    logger.info(f"Seeding schema descriptions from {DOCS_DIR}...")
    schema_count = seed_schemas(store)
    logger.info(f"  → {schema_count} table schemas upserted")

    logger.info(f"Seeding SQL examples from {EXAMPLES_DIR}...")
    example_count = seed_examples(store)
    logger.info(f"  → {example_count} examples upserted")

    logger.info("Seed complete.")
    logger.info(
        f"  schema_descriptions: {store.schema_collection.count()} documents"
    )
    logger.info(
        f"  sql_examples: {store.examples_collection.count()} documents"
    )


if __name__ == "__main__":
    main()
