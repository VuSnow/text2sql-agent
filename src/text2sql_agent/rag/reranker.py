import logging
from dataclasses import dataclass

import boto3

from text2sql_agent.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    index: int
    relevance_score: float
    text: str


class BedrockReranker:
    """AWS Bedrock Cohere Rerank client via bedrock-agent-runtime."""

    def __init__(self) -> None:
        session = boto3.Session(
            region_name=settings.aws_region,
            profile_name=settings.aws_profile,
        )
        self.client = session.client("bedrock-agent-runtime")
        self.model_arn = (
            f"arn:aws:bedrock:{settings.aws_region}::foundation-model/{settings.reranker_model_id}"
        )
        self.top_k = settings.reranker_top_k

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query. Returns top_k results sorted by score."""
        if not documents:
            return []

        k = top_k or self.top_k
        k = min(k, len(documents))

        sources = [
            {
                "type": "INLINE",
                "inlineDocumentSource": {
                    "type": "TEXT",
                    "textDocument": {"text": doc},
                },
            }
            for doc in documents
        ]

        response = self.client.rerank(
            queries=[
                {
                    "type": "TEXT",
                    "textQuery": {"text": query},
                }
            ],
            sources=sources,
            rerankingConfiguration={
                "type": "BEDROCK_RERANKING_MODEL",
                "bedrockRerankingConfiguration": {
                    "modelConfiguration": {
                        "modelArn": self.model_arn,
                    },
                    "numberOfResults": k,
                },
            },
        )

        reranked = []
        for item in response["results"]:
            idx = item["index"]
            reranked.append(RerankResult(
                index=idx,
                relevance_score=item["relevanceScore"],
                text=documents[idx],
            ))

        reranked.sort(key=lambda x: x.relevance_score, reverse=True)
        return reranked
