"""classify_request node — LLM structured output for intent classification."""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from text2sql_agent.agent.state import AgentState
from text2sql_agent.llm.prompts.classification import CLASSIFICATION_SYSTEM_PROMPT
from text2sql_agent.llm.provider import get_llm

logger = logging.getLogger(__name__)


async def classify_request(state: AgentState) -> AgentState:
    """Classify user question intent and determine routing decision.

    Sets state["classification"] with request_type, decision, flags, etc.
    """
    question = state["question"]
    llm = get_llm().bind(response_format={"type": "json_object"})

    messages = [
        SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT),
        HumanMessage(content=question),
    ]

    response = await llm.ainvoke(messages)
    content = response.content.strip()

    # Parse JSON response (strip markdown code fences if present)
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        classification = json.loads(content)
        if not isinstance(classification, dict):
            raise ValueError("Not a JSON object")
    except (json.JSONDecodeError, ValueError):
        logger.error(f"Failed to parse classification response: {content}")
        classification = {
            "request_type": "unsupported",
            "decision": "block",
            "requires_sql": False,
            "flags": {
                "is_destructive": False,
                "is_raw_sql": False,
                "is_prompt_injection": False,
                "is_broad_export": False,
                "needs_clarification": False,
                "is_multi_intent": False,
            },
            "block_reason": "unsupported",
            "reason": "Failed to parse classification response",
        }

    logger.info(
        f"Classification: type={classification['request_type']} "
        f"decision={classification['decision']}"
    )

    return {"classification": classification}
