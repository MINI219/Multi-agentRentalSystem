"""Profile agent — LLM-powered user requirement extraction.

Uses structured output to extract budget, location, and pet_friendly from
the full conversation history. Always re-extracts on every call so the user
can change their mind ("望京呢?", "预算改5000", "所有区域").
"""

from langchain_core.messages import AIMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.base import get_llm
from app.graph.state import RentState


class UserProfileExtraction(BaseModel):
    """Structured user profile extracted from conversation."""

    needs_clarification: bool = Field(
        description=(
            "True if BUDGET cannot be determined from the conversation. "
            "Location may be empty (meaning 'search all areas')."
        )
    )
    clarification_message: str = Field(
        default="",
        description="Natural follow-up question to ask the user (in Chinese) when needs_clarification=True",
    )
    budget: int = Field(
        default=0,
        description="Monthly rent budget in CNY. This is the ONLY mandatory field.",
    )
    location: str = Field(
        default="",
        description=(
            "Preferred district/area. Empty string means 'search all areas'. "
            "When user says '所有区域', '不限', '随便', '都可以', set this to ''."
        ),
    )
    pet_friendly: bool = Field(
        default=False,
        description="True ONLY if the user explicitly mentions pets (猫/狗/宠物 etc.)",
    )


PROFILE_SYSTEM_PROMPT = """You are a rental consultant. Extract the user's rental requirements from
the FULL conversation history (the user may change their mind over time).

Fields to extract:
- **budget** (MANDATORY): monthly rent budget in CNY (integer)
- **location** (OPTIONAL): preferred district/area. EMPTY STRING means search everywhere.
  If user says "所有区域", "不限", "随便", "都可以", "看看有哪些", set location="".
- **pet_friendly**: True ONLY if user explicitly mentions pets.

CRITICAL RULES:
1. ONLY budget is mandatory. If budget is missing → needs_clarification=True.
2. Location CAN be empty (user wants to browse all areas). Do NOT ask for location
   if the user hasn't specified one — just search everywhere.
3. When the user changes a previously-set value (e.g. says "望京呢" or "预算改5000"
   or "所有区域"), you MUST update the corresponding field. The latest preference wins.
4. If the user mentioned a budget range (e.g. "4500左右"), use the upper bound.
5. Read the entire conversation — the user may have provided budget in message #1
   and location in message #3. Extract from ALL messages combined.
6. For pet_friendly: True only for explicit pet mentions (猫/狗/宠物 etc.).
7. Clarification question: ONLY ask about budget. NEVER ask about location."""


async def profile_agent(state: RentState) -> dict:
    """Extract user rental requirements from the full conversation history.

    Always re-runs extraction on every call — the latest user preference wins.
    """
    messages = state.get("messages", [])
    existing_profile = state.get("user_profile") or {}

    # Only skip if the conversation hasn't changed (no new user message).
    # The last message is always from the user when the graph is invoked,
    # so we should always run extraction.
    llm = get_llm()
    structured_llm = llm.with_structured_output(
        UserProfileExtraction, method="function_calling"
    )

    full_messages = [
        SystemMessage(content=PROFILE_SYSTEM_PROMPT),
        *messages,
    ]

    extraction: UserProfileExtraction = await structured_llm.ainvoke(full_messages)

    if extraction.needs_clarification:
        return {
            "messages": [AIMessage(content=extraction.clarification_message)],
            "user_profile": existing_profile,  # keep any partial info
        }

    new_profile = {
        "budget": extraction.budget,
        "location": extraction.location,
        "pet_friendly": extraction.pet_friendly,
    }

    # Build confirmation message
    loc_part = extraction.location if extraction.location else "全区域"
    pet_part = "，需要宠物友好" if extraction.pet_friendly else ""
    confirm_msg = (
        f"好的，已了解：{loc_part}，预算{extraction.budget}元/月{pet_part}。"
        f"正在为您搜索..."
    )

    return {
        "user_profile": new_profile,
        "messages": [AIMessage(content=confirm_msg)],
    }
