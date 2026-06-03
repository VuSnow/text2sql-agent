"""Integration tests for RAG store search and rerank."""

import pytest

from text2sql_agent.rag.store import RAGStore


@pytest.fixture(scope="module")
def store() -> RAGStore:
    """Use the already-seeded ChromaDB store."""
    return RAGStore()


class TestSchemaSearch:
    """Test schema_descriptions collection search."""

    def test_search_returns_results(self, store: RAGStore):
        results = store.search_schemas("khách hàng nào có số dư cao nhất?")
        assert len(results) > 0

    def test_search_finds_customers_table(self, store: RAGStore):
        results = store.search_schemas("thông tin khách hàng, tên, số điện thoại")
        table_names = [r.table_name for r in results]
        assert "customers" in table_names

    def test_search_finds_transactions_table(self, store: RAGStore):
        results = store.search_schemas("giao dịch chuyển khoản tháng này")
        table_names = [r.table_name for r in results]
        assert "transactions" in table_names

    def test_search_finds_fraud_tables(self, store: RAGStore):
        results = store.search_schemas("báo cáo gian lận, fraud report")
        table_names = [r.table_name for r in results]
        assert "fraud_reports" in table_names

    def test_search_finds_cards(self, store: RAGStore):
        results = store.search_schemas("thẻ tín dụng, thẻ ghi nợ, visa, mastercard")
        table_names = [r.table_name for r in results]
        assert "cards" in table_names

    def test_search_with_rerank_has_scores(self, store: RAGStore):
        results = store.search_schemas("thanh toán hóa đơn điện nước")
        assert all(r.score > 0 for r in results)

    def test_search_without_rerank(self, store: RAGStore):
        results = store.search_schemas("tài khoản tiết kiệm", rerank=False)
        assert len(results) > 0
        table_names = [r.table_name for r in results]
        assert "accounts" in table_names


class TestExampleSearch:
    """Test sql_examples collection search."""

    def test_search_returns_results(self, store: RAGStore):
        results = store.search_examples("tổng chi tiêu tháng này")
        assert len(results) > 0

    def test_search_returns_sql(self, store: RAGStore):
        results = store.search_examples("liệt kê giao dịch chuyển khoản")
        assert all(r.sql != "" for r in results)

    def test_search_returns_tables_metadata(self, store: RAGStore):
        results = store.search_examples("khách hàng chi tiêu nhiều nhất")
        assert all(len(r.tables) > 0 for r in results)

    def test_search_with_table_filter(self, store: RAGStore):
        results = store.search_examples(
            "giao dịch gần đây",
            table_filter=["transactions"],
        )
        assert len(results) > 0
        # All results should involve transactions table
        for r in results:
            assert "transactions" in r.tables

    def test_search_with_fraud_filter(self, store: RAGStore):
        results = store.search_examples(
            "báo cáo gian lận",
            table_filter=["fraud_reports"],
        )
        assert len(results) > 0
        for r in results:
            assert "fraud_reports" in r.tables

    def test_search_complexity_metadata(self, store: RAGStore):
        results = store.search_examples("window function ranking")
        complexities = {r.complexity for r in results}
        # Should find complex examples for window functions
        assert "complex" in complexities

    def test_search_with_rerank_sorted_by_score(self, store: RAGStore):
        results = store.search_examples("số dư tài khoản")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_without_rerank(self, store: RAGStore):
        results = store.search_examples(
            "thẻ hết hạn",
            rerank=False,
        )
        assert len(results) > 0
