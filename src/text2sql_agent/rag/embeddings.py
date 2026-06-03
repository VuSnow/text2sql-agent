import json
import logging

import boto3

from text2sql_agent.config import settings

logger = logging.getLogger(__name__)


class BedrockEmbeddings:
    """AWS Bedrock Titan Embed V2 client."""

    def __init__(self) -> None:
        session = boto3.Session(
            region_name=settings.aws_region,
            profile_name=settings.aws_profile,
        )
        self.client = session.client("bedrock-runtime")
        self.model_id = settings.embedding_model_id
        self.dimensions = settings.embedding_dimensions

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        body = json.dumps({
            "inputText": text,
            "dimensions": self.dimensions,
            "normalize": True,
        })
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Calls API sequentially (Titan doesn't support batch)."""
        embeddings = []
        for text in texts:
            embeddings.append(self.embed_text(text))
        return embeddings
