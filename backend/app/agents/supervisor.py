"""Supervisor agent — rule-based routing.

Only budget is mandatory. Location can be empty (search all areas).
"""

from app.graph.state import RentState


async def supervisor_agent(state: RentState) -> dict:
    """Determine the next agent based on the current state."""
    user_profile = state.get("user_profile") or {}
    candidates = state.get("candidate_properties") or []
    recommended = state.get("recommended_properties") or []

    profile_done = "user_profile" in state
    search_done = "candidate_properties" in state
    recommend_done = "recommended_properties" in state

    # Route 1: profile not yet attempted
    if not profile_done:
        return {
            "next_agent": "profile",
            "supervisor_reasoning": "尚未收集用户需求",
        }

    # Route 2: budget is mandatory; location is optional
    if not user_profile.get("budget"):
        return {
            "next_agent": "FINISH",
            "supervisor_reasoning": "预算未明确，等待用户补充",
        }

    # Route 3: search not yet attempted → search (with or without location)
    if not search_done:
        loc = user_profile.get("location") or "全区域"
        return {
            "next_agent": "search",
            "supervisor_reasoning": f"需求已收集，在{loc}搜索",
        }

    # Route 4: search done but 0 results → FINISH
    if not candidates:
        loc = user_profile.get("location") or "全区域"
        return {
            "next_agent": "FINISH",
            "supervisor_reasoning": f"{loc}无匹配房源",
        }

    # Route 5: candidates exist but not scored → recommend
    if not recommend_done:
        return {
            "next_agent": "recommend",
            "supervisor_reasoning": f"已有{len(candidates)}个候选房源，需要打分",
        }

    # Route 6: everything done
    return {
        "next_agent": "FINISH",
        "supervisor_reasoning": "所有步骤完成",
    }
