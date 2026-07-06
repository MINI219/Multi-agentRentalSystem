"""Search agent — queries properties via MCP server.

Connects to the RentalTools MCP server over stdio, binds its tool to the
LLM, and lets the LLM decide how to call search_properties based on the
user profile.
"""

import json
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

from app.agents.base import get_llm
from app.graph.state import RentState

SEARCH_SYSTEM_PROMPT = """You are a property search assistant. Use the search_properties tool to find
rental properties matching the user's requirements.

The user profile provides:
- location: the target district/area
- budget: the maximum monthly rent in CNY
- pet_friendly: whether pet-friendly housing is needed

Call search_properties with exactly these parameters:
  location = user's location
  max_budget = user's budget
  pet_friendly = user's pet_friendly flag (true/false)

After receiving results, summarize what you found in Chinese."""


def _parse_mcp_result(raw: list) -> list[dict]:
    """Parse MCP content-block results into a list of property dicts.

    MCP tools return results as content blocks like:
        [{"type": "text", "text": '{"id": "...", ...}', "id": "lc_..."}, ...]

    Each block's ``text`` field is a JSON-encoded property dict.
    """
    properties: list[dict] = []
    for block in raw:
        if not isinstance(block, dict):
            continue
        text = block.get("text", "")
        if not text:
            continue
        try:
            prop = json.loads(text)
            if isinstance(prop, dict):
                properties.append(prop)
        except json.JSONDecodeError:
            properties.append({"title": text[:80], "raw": text})
    return properties


async def search_agent(state: RentState) -> dict:
    """Connect to MCP server, bind search tool to LLM, execute search.

    Returns ``candidate_properties`` from the MCP tool result.
    """
    user_profile = state.get("user_profile") or {}

    location = user_profile.get("location", "")
    budget = user_profile.get("budget", 0)
    pet_friendly = user_profile.get("pet_friendly", False)

    # Resolve MCP server path relative to this file
    # search_agent.py → agents/ → app/ → backend/ → project root/
    server_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "mcp_server", "server.py"
        )
    )

    server_params = StdioServerParameters(
        command="python",
        args=[server_path],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)

            llm = get_llm()
            llm_with_tools = llm.bind_tools(tools)

            messages = [
                SystemMessage(content=SEARCH_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"User profile:\n"
                        f"  - location: {location}\n"
                        f"  - budget: {budget} CNY/month\n"
                        f"  - pet_friendly: {pet_friendly}\n\n"
                        f"Please search for matching properties."
                    )
                ),
            ]

            response = await llm_with_tools.ainvoke(messages)

            # Execute any tool calls the LLM made
            candidate_properties: list[dict] = []
            tool_map = {tool.name: tool for tool in tools}

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                if tool_name in tool_map:
                    raw = await tool_map[tool_name].ainvoke(tool_args)

                    # MCP returns content blocks: [{"type":"text", "text":"...", "id":"..."}]
                    if isinstance(raw, list):
                        candidate_properties.extend(_parse_mcp_result(raw))
                    elif isinstance(raw, str):
                        try:
                            parsed = json.loads(raw)
                            if isinstance(parsed, list):
                                candidate_properties.extend(_parse_mcp_result(parsed))
                            elif isinstance(parsed, dict):
                                candidate_properties.append(parsed)
                        except json.JSONDecodeError:
                            candidate_properties.append({"title": raw[:80], "raw": raw})

            summary = (
                f"已为您在{location}附近找到{len(candidate_properties)}处房源，"
                f"预算{budget}元/月以内"
                f"{'，已筛选宠物友好' if pet_friendly else ''}。"
            )

            return {
                "candidate_properties": candidate_properties,
                "messages": [AIMessage(content=summary)],
            }
