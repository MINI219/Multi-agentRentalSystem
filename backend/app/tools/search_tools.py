"""Search-related tools for the rental agents.

In a production system, these would connect to a real property database or
external API. For now, they serve as placeholders that agents can call via
LangChain tool integration.
"""

from typing import Optional

from pydantic import BaseModel, Field


class SearchInput(BaseModel):
    """Input schema for the property search tool."""

    city: str = Field(description="Target city")
    district: Optional[str] = Field(default=None, description="Specific district")
    budget_min: Optional[int] = Field(default=None, description="Minimum monthly rent (CNY)")
    budget_max: Optional[int] = Field(default=None, description="Maximum monthly rent (CNY)")
    room_count: Optional[int] = Field(default=None, description="Number of bedrooms")
    keywords: Optional[list[str]] = Field(default=None, description="Extra search keywords")


async def search_properties(params: SearchInput) -> list[dict]:
    """Search for rental properties matching the given criteria.

    TODO: Replace with real database query or external API call.
    """
    # Placeholder — in production this would query a database
    return []


# Tool registry for LangChain agent integration
AVAILABLE_TOOLS: list[dict] = [
    {
        "name": "search_properties",
        "description": "Search rental property listings by city, budget, and preferences",
        "parameters": SearchInput,
        "function": search_properties,
    },
]
