"""repair_sql node — LLM repairs broken SQL using error context."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from text2sql_agent.agent.state import AgentState
from text2sql_agent.llm.prompts.repair import REPAIR_SYSTEM_PROMPT
from text2sql_agent.llm.provider import get_llm

logger = logging.getLogger(__name__)


async def repair_sql(state: AgentState) -> AgentState:
    """Repair broken SQL using error context from validation or semantic check.

    Increments state["repair_attempts"] and updates state["generated_sql"].
    """
    question = state["question"]
    sql = state.get("generated_sql", "")
    schema_context = state.get("schema_context", "")
    repair_attempts = state.get("repair_attempts", 0)

    # Get error details from validation or semantic check
    validation = state.get("validation_result", {})
    semantic = state.get("semantic_check", {})

    if validation and not validation.get("valid"):
        error_type = validation.get("error_type", "unknown")
        error_message = validation.get("error_message", "Unknown error")
    elif semantic and not semantic.get("passed"):
        error_type = "semantic"
        # Use repair_instruction if available, fallback to issues
        repair_instruction = semantic.get("repair_instruction")
        issues = semantic.get("issues", [])
        if repair_instruction:
            error_message = repair_instruction
        elif issues:
            error_message = "; ".join(
                i["message"] if isinstance(i, dict) else str(i) for i in issues
            )
        else:
            error_message = "Semantic check failed"
        # Use suggestion if available
        suggestion = semantic.get("suggestion")
        if suggestion:
            logger.info("Using semantic check suggestion as repair")
            return {
                "generated_sql": suggestion.rstrip(";"),
                "repair_attempts": repair_attempts + 1,
            }
    else:
        error_type = "unknown"
        error_message = "Unknown error"

    prompt = REPAIR_SYSTEM_PROMPT.format(
        schema_context=schema_context,
        question=question,
        sql=sql,
        error_type=error_type,
        error_message=error_message,
    )

    llm = get_llm()
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Fix this SQL:\n{sql}\n\nError: {error_message}"),
    ]

    response = await llm.ainvoke(messages)
    fixed_sql = response.content.strip()

    if fixed_sql.startswith("```"):
        fixed_sql = fixed_sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    fixed_sql = fixed_sql.rstrip(";")

    logger.info(f"Repair attempt {repair_attempts + 1}: {len(fixed_sql)} chars")

    return {
        "generated_sql": fixed_sql,
        "repair_attempts": repair_attempts + 1,
    }
