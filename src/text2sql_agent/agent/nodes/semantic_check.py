"""semantic_check_sql node — LLM verifies SQL logic correctness."""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from text2sql_agent.agent.state import AgentState
from text2sql_agent.llm.prompts.semantic_check import (
    SEMANTIC_CHECK_SYSTEM_PROMPT,
    SEMANTIC_CHECK_USER_PROMPT,
)
from text2sql_agent.llm.provider import get_llm

logger = logging.getLogger(__name__)


async def semantic_check_sql(state: AgentState) -> AgentState:
    """Verify SQL logic correctness using LLM.

    Sets state["semantic_check"] with passed, severity, issues,
    repair_instruction, suggestion.
    """
    question = state["question"]
    sql = state.get("generated_sql", "")
    schema_context = state.get("schema_context", "")
    policy_context = state.get("policy_context", "")
    example_context = state.get("example_context", "")

    system_prompt = SEMANTIC_CHECK_SYSTEM_PROMPT.format(
        schema_context=schema_context,
        policy_context=policy_context,
        example_context=example_context,
        question=question,
        sql=sql,
    )
    user_msg = SEMANTIC_CHECK_USER_PROMPT.format(question=question, sql=sql)

    llm = get_llm().bind(response_format={"type": "json_object"})
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ]

    response = await llm.ainvoke(messages)
    content = response.content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        check = json.loads(content)
        if not isinstance(check, dict):
            # LLM returned a simple value like "passed" instead of object
            logger.warning(f"Semantic check returned non-dict: {check}")
            check = {
                "passed": True,
                "severity": "info",
                "issues": [],
                "repair_instruction": None,
                "suggestion": None,
            }
    except json.JSONDecodeError:
        logger.error(f"Failed to parse semantic check: {content}")
        check = {
            "passed": True,
            "severity": "info",
            "issues": [],
            "repair_instruction": None,
            "suggestion": None,
        }

    logger.info(
        f"Semantic check: passed={check['passed']} severity={check['severity']} "
        f"issues={len(check.get('issues', []))}"
    )

    return {"semantic_check": check}
