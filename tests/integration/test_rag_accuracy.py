"""Accuracy tests for RAG search — verifies semantic relevance of results."""

import pytest

from text2sql_agent.rag.store import RAGStore


@pytest.fixture(scope="module")
def store() -> RAGStore:
    return RAGStore()


class TestSchemaSearchAccuracy:
    """Verify schema search returns correct tables for NL queries."""

    @pytest.mark.parametrize(
        "query,expected_tables",
        [
            ("Khách hàng nào bị khóa tài khoản?", ["customers"]),
            ("Giao dịch chuyển khoản tháng này", ["transactions"]),
            ("Thẻ tín dụng hết hạn", ["cards"]),
            (
                "Thanh toán hóa đơn điện nước",
                ["billers", "customer_biller_accounts", "transactions"],
            ),
            (
                "Báo cáo gian lận và quyết định xử lý",
                ["fraud_reports", "fraud_decisions"],
            ),
            ("Số dư tài khoản tiết kiệm", ["accounts"]),
            ("Người thụ hưởng chuyển khoản", ["beneficiaries"]),
            ("Lịch sử audit hệ thống", ["audit_logs"]),
            ("API call bị lỗi", ["api_call_logs"]),
            ("Yêu cầu khóa thẻ đang chờ OTP", ["action_requests", "cards"]),
        ],
    )
    def test_schema_search_finds_expected_tables(
        self, store: RAGStore, query: str, expected_tables: list[str]
    ):
        results = store.search_schemas(query, top_k=5)
        found_tables = [r.table_name for r in results]
        for table in expected_tables:
            assert table in found_tables, (
                f"Query '{query}': expected '{table}' in top 5, got {found_tables}"
            )


class TestExampleSearchAccuracy:
    """Verify example search returns relevant SQL examples."""

    @pytest.mark.parametrize(
        "query,expected_table",
        [
            ("Tổng chi tiêu tháng này của khách hàng", "transactions"),
            ("Thẻ bị khóa", "cards"),
            ("Giao dịch chuyển khoản lớn nhất", "transactions"),
            ("Hóa đơn chưa thanh toán", "billers"),
            ("Khách hàng bị report gian lận nhiều lần", "fraud_reports"),
        ],
    )
    def test_example_search_finds_relevant_table(
        self, store: RAGStore, query: str, expected_table: str
    ):
        results = store.search_examples(query, top_k=3)
        assert len(results) > 0, f"No results for query '{query}'"
        has_match = any(expected_table in r.tables for r in results)
        assert has_match, (
            f"Query '{query}': expected table '{expected_table}' in top 3 results, "
            f"got {[r.tables for r in results]}"
        )

    @pytest.mark.parametrize(
        "query,table_filter,min_results",
        [
            ("chi tiêu nhiều nhất", ["transactions", "customers"], 3),
            ("thẻ hết hạn", ["cards"], 3),
            ("fraud report mới nhất", ["fraud_reports", "fraud_decisions"], 3),
        ],
    )
    def test_example_search_with_table_filter(
        self,
        store: RAGStore,
        query: str,
        table_filter: list[str],
        min_results: int,
    ):
        results = store.search_examples(query, table_filter=table_filter, top_k=10)
        assert len(results) >= min_results, (
            f"Query '{query}' with filter {table_filter}: "
            f"expected >= {min_results} results, got {len(results)}"
        )
        # All results must contain at least one filtered table
        for r in results:
            overlap = set(r.tables) & set(table_filter)
            assert overlap, (
                f"Result tables {r.tables} has no overlap with filter {table_filter}"
            )

    def test_top1_relevance_score_above_threshold(self, store: RAGStore):
        """Top 1 result should have reasonable similarity score."""
        results = store.search_examples("giao dịch chuyển khoản ngân hàng", top_k=1)
        assert len(results) == 1
        assert results[0].score > 0.3, (
            f"Top 1 score {results[0].score:.4f} too low, expected > 0.3"
        )

    def test_results_sorted_by_score_descending(self, store: RAGStore):
        results = store.search_examples("số dư tài khoản khách hàng", top_k=5)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
