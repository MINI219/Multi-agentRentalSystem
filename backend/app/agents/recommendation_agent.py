"""Recommendation agent — evaluates & ranks candidate properties (mock phase).

Reads candidate_properties, adds a score field, and stores in
recommended_properties.
"""

from langchain_core.messages import AIMessage

from app.graph.state import RentState


async def recommendation_agent(state: RentState) -> dict:
    """Score each candidate property and produce ranked recommendations."""
    candidates = state.get("candidate_properties") or []

    if not candidates:
        return {
            "messages": [AIMessage(content="暂无可评估的房源，请先进行搜索。")],
        }

    # Simple mock scoring based on price and area
    scored = []
    for i, prop in enumerate(candidates):
        price = prop.get("price", 5000)
        area = prop.get("area_sqm", 50)
        # Mock score: lower price + larger area → higher score
        score = round(min(10, (5000 / price) * 5 + (area / 100) * 5), 1)
        scored.append({**prop, "score": score, "rank": i + 1})

    # Sort by score descending
    scored.sort(key=lambda p: p["score"], reverse=True)
    for i, p in enumerate(scored):
        p["rank"] = i + 1

    return {
        "recommended_properties": scored,
        "messages": [AIMessage(content="已为您找到推荐房源，请查看右侧卡片。")],
    }
