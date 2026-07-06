"""LangGraph StateGraph — multi-agent orchestration engine.

Graph topology (Supervisor routing pattern):

    START -> [supervisor]
                |
        +-------+--------+
        v       v        v        v
    [profile] [search] [recommend] END
        |       |        |
        +-------+--------+
                v
          [supervisor]  (loop until FINISH)

Every worker node returns to supervisor for the next routing decision.
"""

from langgraph.graph import END, StateGraph

from app.agents.profile_agent import profile_agent as profile_node
from app.agents.recommendation_agent import recommendation_agent as recommend_node
from app.agents.search_agent import search_agent as search_node
from app.agents.supervisor import supervisor_agent as supervisor_node
from app.graph.state import RentState


# ---- Routing function ----


def route_by_supervisor(state: RentState) -> str:
    """Map supervisor's next_agent decision to the next node (or END)."""
    next_agent = state.get("next_agent", "profile")

    if next_agent == "FINISH":
        return END

    # next_agent is one of: 'profile', 'search', 'recommend'
    return next_agent


# ---- Graph construction ----


def build_graph():
    """Build and compile the multi-agent rental graph."""

    workflow = StateGraph(RentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("profile", profile_node)
    workflow.add_node("search", search_node)
    workflow.add_node("recommend", recommend_node)

    # Entry point
    workflow.set_entry_point("supervisor")

    # All worker nodes route back to supervisor after execution
    workflow.add_edge("profile", "supervisor")
    workflow.add_edge("search", "supervisor")
    workflow.add_edge("recommend", "supervisor")

    # Supervisor conditionally routes to worker node or END
    workflow.add_conditional_edges(
        "supervisor",
        route_by_supervisor,
        {
            "profile": "profile",
            "search": "search",
            "recommend": "recommend",
            END: END,
        },
    )

    return workflow.compile()


# Module-level compiled graph (imported by API routes)
rental_graph = build_graph()


# ---- Test harness ----

if __name__ == "__main__":
    import asyncio
    from langchain_core.messages import HumanMessage

    async def main():
        print("=" * 60)
        print("  Multi-Agent Rental System - Graph Flow Test")
        print("=" * 60)

        # Initial state with the user's rental request
        # Do NOT set user_profile / candidate_properties / recommended_properties —
        # the supervisor uses key absence to detect "not yet attempted".
        initial_state: RentState = {
            "messages": [
                HumanMessage(
                    content="我想在九堡附近租个房子，预算大概3000左右，我有一只猫。"
                )
            ],
            "next_agent": "",
        }

        print("\n[INPUT] '我想在九堡附近租个房子，预算大概3000左右，我有一只猫。'")
        print(f"        user_profile = {initial_state.get('user_profile', {})}")
        print(f"        candidate_properties = {initial_state.get('candidate_properties', 'NOT SET')}")
        print(f"        recommended_properties = {initial_state.get('recommended_properties', 'NOT SET')}")
        print("\n" + "-" * 60)

        step = 0
        async for event in rental_graph.astream(
            initial_state,
            {"recursion_limit": 20},
        ):
            step += 1
            node_name = list(event.keys())[0]
            node_state = event[node_name]

            print(f"\n>>> Step {step}: Node [{node_name}]")

            # Show next_agent decision
            if "next_agent" in node_state:
                print(f"    supervisor routes to: {node_state['next_agent']}")

            # Show latest message
            msgs = node_state.get("messages", [])
            if msgs:
                last_msg = msgs[-1]
                content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                # Truncate long messages for readability
                if len(content) > 120:
                    content = content[:120] + "..."
                print(f"    message: {content}")

            # Show key data
            if "user_profile" in node_state and node_state["user_profile"]:
                print(f"    user_profile: {node_state['user_profile']}")
            if "candidate_properties" in node_state and node_state["candidate_properties"]:
                print(f"    candidate_properties: {len(node_state['candidate_properties'])} items")
                for p in node_state["candidate_properties"]:
                    title = p.get('title', p.get('id', '?'))
                    price = p.get('price', '?')
                    pet = p.get('pet_friendly', '?')
                    print(f"      - {title} | {price} CNY/mo | pet_friendly={pet}")
            if "recommended_properties" in node_state and node_state["recommended_properties"]:
                recs = node_state["recommended_properties"]
                print(f"    recommended_properties: {len(recs)} items")
                for p in recs:
                    title = p.get('title', p.get('id', '?'))
                    price = p.get('price', '?')
                    score = p.get('score', 'N/A')
                    rank = p.get('rank', '?')
                    print(f"      - {title} | {price} CNY/mo | score: {score} | rank: #{rank}")

        print("\n" + "=" * 60)
        print("  [OK] Flow complete - all steps executed")
        print("=" * 60)

    asyncio.run(main())
