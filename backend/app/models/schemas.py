"""FastAPI request / response schemas.

These define the shape of data sent over the REST API — distinct from the
internal RentState (graph/state.py) which drives LangGraph execution.
"""

from typing import Optional

from pydantic import BaseModel, Field


# ---- Request ----


class ChatRequest(BaseModel):
    """Incoming chat message from the frontend."""

    message: str = Field(..., description="User's chat message", min_length=1)
    session_id: Optional[str] = Field(
        default=None, description="Existing session ID for conversation continuity"
    )


# ---- Response ----


class PropertyResponse(BaseModel):
    """A rental property as returned to the frontend.

    Matches the fields produced by the MCP server from properties.csv.
    """

    id: str
    title: str
    location: str = ""
    price: int
    size: float = 0.0
    bedrooms: str = ""
    pet_friendly: bool = False
    description: str = ""
    score: Optional[float] = None
    rank: Optional[int] = None


class ChatResponse(BaseModel):
    """Response returned after processing a user message."""

    session_id: str
    reply: str
    next_agent: Optional[str] = None
    properties: list[PropertyResponse] = []
    user_profile: Optional[dict] = None


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str
    version: str
