import logging
from dataclasses import dataclass

import chromadb

from text2sql_agent.config import settings
from text2sql_agent.rag.embeddings import BedrockEmbeddings
from text2sql_agent.rag.reranker import BedrockReranker, RerankResult

logger = logging.getLogger(__name__)


@dataclass
class SchemaSearchResult:
    table_name: str
    description: str
    score: float


@dataclass
class ExampleSearchResult:
    question: str
    sql: str
    tables: list[str]
    complexity: str
    explanation: str
    score: float


class RAGStore:
    """ChromaDB-backed RAG store with Bedrock embeddings and reranking."""

    def __init__(self) -> None:
        settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
        self.embeddings = BedrockEmbeddings()
        self.reranker = BedrockReranker() if settings.reranker_enabled else None

        # Get or create collections (no embedding function — we manage embeddings manually)
        self.schema_collection = self.client.get_or_create_collection(
            name=settings.rag_schema_collection,
            metadata={"hnsw:space": "cosine"},
        )
        self.examples_collection = self.client.get_or_create_collection(
            name=settings.rag_examples_collection,
            metadata={"hnsw:space": "cosine"},
        )

    # ─── Schema Collection ───────────────────────────────────────────────

    def upsert_schema(
        self,
        table_name: str,
        description: str,
        full_text: str,
    ) -> None:
        """Upsert a table schema document."""
        embedding = self.embeddings.embed_text(full_text)
        self.schema_collection.upsert(
            ids=[table_name],
            embeddings=[embedding],
            documents=[full_text],
            metadatas=[{"table_name": table_name, "description": description}],
        )

    def search_schemas(
        self,
        query: str,
        top_k: int | None = None,
        rerank: bool = True,
    ) -> list[SchemaSearchResult]:
        """Search for relevant tables given a NL question."""
        k = top_k or settings.rag_top_k
        query_embedding = self.embeddings.embed_text(query)

        results = self.schema_collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, self.schema_collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"][0]:
            return []

        if rerank and self.reranker and results["documents"][0]:
            reranked = self.reranker.rerank(
                query=query,
                documents=results["documents"][0],
                top_k=settings.reranker_top_k,
            )
            return self._map_schema_reranked(results, reranked)

        # No rerank — return by cosine distance
        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            output.append(SchemaSearchResult(
                table_name=doc_id,
                description=results["metadatas"][0][i].get("description", ""),
                score=1 - results["distances"][0][i],  # cosine distance → similarity
            ))
        return output

    # ─── Examples Collection ─────────────────────────────────────────────

    def upsert_example(
        self,
        example_id: str,
        question: str,
        sql: str,
        tables: list[str],
        complexity: str,
        explanation: str,
        full_text: str,
    ) -> None:
        """Upsert an SQL example document."""
        embedding = self.embeddings.embed_text(full_text)
        self.examples_collection.upsert(
            ids=[example_id],
            embeddings=[embedding],
            documents=[full_text],
            metadatas=[{
                "question": question,
                "sql": sql,
                "tables": ",".join(tables),
                "complexity": complexity,
                "explanation": explanation,
            }],
        )

    def search_examples(
        self,
        query: str,
        table_filter: list[str] | None = None,
        top_k: int | None = None,
        rerank: bool = True,
    ) -> list[ExampleSearchResult]:
        """Search for relevant SQL examples. Optionally filter by tables used."""
        k = top_k or settings.rag_top_k
        query_embedding = self.embeddings.embed_text(query)

        count = self.examples_collection.count()
        if count == 0:
            return []

        # Fetch more results if filtering, then post-filter
        fetch_k = min(k * 3, count) if table_filter else min(k, count)

        results = self.examples_collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_k,
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"][0]:
            return []

        # Post-filter by table overlap
        if table_filter:
            filtered_indices = []
            for i, meta in enumerate(results["metadatas"][0]):
                doc_tables = meta.get("tables", "").split(",")
                if any(t in doc_tables for t in table_filter):
                    filtered_indices.append(i)
            # Rebuild results with only matching indices
            results = {
                "ids": [[results["ids"][0][i] for i in filtered_indices]],
                "documents": [[results["documents"][0][i] for i in filtered_indices]],
                "metadatas": [[results["metadatas"][0][i] for i in filtered_indices]],
                "distances": [[results["distances"][0][i] for i in filtered_indices]],
            }
            if not results["ids"][0]:
                return []

        if rerank and self.reranker and results["documents"][0]:
            reranked = self.reranker.rerank(
                query=query,
                documents=results["documents"][0],
                top_k=settings.reranker_top_k,
            )
            return self._map_examples_reranked(results, reranked)

        # No rerank
        output = []
        for i, _ in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            output.append(ExampleSearchResult(
                question=meta.get("question", ""),
                sql=meta.get("sql", ""),
                tables=meta.get("tables", "").split(","),
                complexity=meta.get("complexity", ""),
                explanation=meta.get("explanation", ""),
                score=1 - results["distances"][0][i],
            ))
        return output

    # ─── Helpers ─────────────────────────────────────────────────────────

    def _map_schema_reranked(
        self,
        raw_results: dict,
        reranked: list[RerankResult],
    ) -> list[SchemaSearchResult]:
        output = []
        for r in reranked:
            idx = r.index
            output.append(SchemaSearchResult(
                table_name=raw_results["ids"][0][idx],
                description=raw_results["metadatas"][0][idx].get("description", ""),
                score=r.relevance_score,
            ))
        return output

    def _map_examples_reranked(
        self,
        raw_results: dict,
        reranked: list[RerankResult],
    ) -> list[ExampleSearchResult]:
        output = []
        for r in reranked:
            idx = r.index
            meta = raw_results["metadatas"][0][idx]
            output.append(ExampleSearchResult(
                question=meta.get("question", ""),
                sql=meta.get("sql", ""),
                tables=meta.get("tables", "").split(","),
                complexity=meta.get("complexity", ""),
                explanation=meta.get("explanation", ""),
                score=r.relevance_score,
            ))
        return output
