"""generate_sql node — LLM generates SQL from question + schema + examples."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from text2sql_agent.agent.state import AgentState
from text2sql_agent.llm.prompts.generation import (
    GENERATION_SYSTEM_PROMPT,
    GENERATION_USER_PROMPT,
)
from text2sql_agent.llm.provider import get_llm

logger = logging.getLogger(__name__)


async def generate_sql(state: AgentState) -> AgentState:
    """Generate SQL query using LLM with schema and example context.

    Sets state["generated_sql"].
    """
    question = state["question"]
    schema_context = state.get("schema_context", "")
    example_context = state.get("example_context", "")
    policy_context = state.get("policy_context", "")

    system_prompt = GENERATION_SYSTEM_PROMPT.format(
        schema_context=schema_context,
        example_context=example_context,
        policy_context=policy_context,
        question=question,
    )
    user_msg = GENERATION_USER_PROMPT.format(question=question)

    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ]

    response = await llm.ainvoke(messages)
    sql = response.content.strip()

    # Strip markdown code fences if present
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Remove trailing semicolons for dry_run compatibility
    sql = sql.rstrip(";")

    logger.info(f"Generated SQL ({len(sql)} chars)")

    return {"generated_sql": sql}
