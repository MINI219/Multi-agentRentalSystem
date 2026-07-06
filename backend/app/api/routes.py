"""API routes exposing the multi-agent rental system."""

import uuid
from fastapi import APIRouter
from langchain_core.messages import HumanMessage

from app.graph.rental_graph import rental_graph
from app.graph.state import RentState
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory session store — maps session_id → accumulated messages
# (Production: replace with Redis / DB)
# ---------------------------------------------------------------------------
_sessions: dict[str, list] = {}


def _get_or_create_session(session_id: str | None) -> tuple[str, list]:
    """Return (session_id, message_history) for the session."""
    sid = session_id or str(uuid.uuid4())
    if sid not in _sessions:
        _sessions[sid] = []
    return sid, _sessions[sid]


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint.

    Accumulates conversation history per session so the profile agent
    sees the full context across multiple turns.
    """

    sid, history = _get_or_create_session(request.session_id)

    # Append the new user message to session history
    user_msg = HumanMessage(content=request.message)
    history.append(user_msg)

    # Build state from accumulated history; reset task-specific keys
    initial_state: RentState = {
        "messages": list(history),  # full conversation so far
        "next_agent": "",
    }

    # Run the graph
    result = await rental_graph.ainvoke(
        initial_state,
        {"recursion_limit": 20},
    )

    # Persist all resulting messages back to the session store
    _sessions[sid] = list(result.get("messages", history))

    # Extract the last assistant message as the reply
    messages = result.get("messages", [])
    reply = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai":
            reply = msg.content
            break

    return ChatResponse(
        session_id=sid,
        reply=reply,
        next_agent=result.get("next_agent"),
        properties=result.get("recommended_properties", []),
        user_profile=result.get("user_profile"),
    )
