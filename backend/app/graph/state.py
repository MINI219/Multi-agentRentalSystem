"""Global RentState definition for the LangGraph state graph.

The shared state that flows through every node in the multi-agent rental system.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class RentState(TypedDict, total=False):
    """Shared state flowing through every node in the rental graph.

    Fields
    ------
    messages : list[BaseMessage]
        Full conversation history. The add_messages reducer appends new
        messages rather than replacing the list.
    user_profile : dict
        Rental requirements gathered by the profile agent.
        Expected keys: budget, location, preferences, etc.
    candidate_properties : list[dict]
        Raw property listings returned by the search agent.
    recommended_properties : list[dict]
        Properties scored & ranked by the recommendation agent.
    next_agent : str
        The agent the supervisor decided to invoke next.
        One of: 'profile', 'search', 'recommend', 'FINISH'.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_profile: dict
    candidate_properties: list[dict]
    recommended_properties: list[dict]
    next_agent: str
