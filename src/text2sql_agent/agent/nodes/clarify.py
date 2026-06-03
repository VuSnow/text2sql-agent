"""clarify_question node — generates clarification questions for ambiguous requests."""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from text2sql_agent.agent.state import AgentState
from text2sql_agent.llm.prompts.clarification import (
    CLARIFICATION_SYSTEM_PROMPT,
    CLARIFICATION_USER_PROMPT,
)
from text2sql_agent.llm.provider import get_llm

logger = logging.getLogger(__name__)


async def clarify_question(state: AgentState) -> AgentState:
    """Generate clarification questions for ambiguous user input.

    Sets state["clarification_questions"] and state["response"].
    """
    question = state["question"]
    classification = state.get("classification", {})

    llm = get_llm()

    user_msg = CLARIFICATION_USER_PROMPT.format(
        question=question,
        classification_result=json.dumps(classification, ensure_ascii=False, indent=2),
    )
    messages = [
        SystemMessage(content=CLARIFICATION_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = await llm.ainvoke(messages)
    content = response.content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        questions = json.loads(content)
    except json.JSONDecodeError:
        questions = ["Bạn có thể mô tả cụ thể hơn câu hỏi không?"]

    # Empty array means blocked request — should not clarify
    if not questions:
        return {
            "clarification_questions": [],
            "response": classification.get("block_reason", "Không thể xử lý yêu cầu này."),
        }

    logger.info(f"Clarification questions: {questions}")

    formatted = "Tôi cần thêm thông tin để trả lời:\n" + "\n".join(
        f"- {q}" for q in questions
    )

    return {
        "clarification_questions": questions,
        "response": formatted,
    }
