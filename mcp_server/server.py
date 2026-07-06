"""RentalTools MCP Server — exposes property search as an MCP tool.

Loads real rental listings from properties.csv at startup and serves them
via the ``search_properties`` tool over stdio transport.
"""

import csv
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("RentalTools")

# ---------------------------------------------------------------------------
# Startup: load properties.csv → PROPERTIES_DB
# ---------------------------------------------------------------------------

CSV_PATH = os.path.join(os.path.dirname(__file__), "properties.csv")

# Keywords that suggest the property is pet-friendly even when the
# pet_friendly column says False
_PET_KEYWORDS = ["宠物", "养猫", "养狗", "可养猫", "可养狗", "猫", "狗", "宠物友好"]

# Prices above this threshold are considered data errors and skipped
_MAX_VALID_PRICE = 100_000


def _looks_pet_friendly(title: str, description: str) -> bool:
    """Return True if title or description contains pet-related keywords."""
    combined = f"{title} {description}"
    return any(kw in combined for kw in _PET_KEYWORDS)


def _load_properties(csv_path: str) -> list[dict]:
    """Load and clean property data from CSV.

    Returns a list of property dicts. Rows with unparseable or
    abnormally large prices are skipped.
    """
    properties: list[dict] = []

    if not os.path.exists(csv_path):
        import sys
        print(f"[WARN] {csv_path} not found — using empty database", file=sys.stderr, flush=True)
        return properties

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # --- price: int, skip anomalies ---
            try:
                price = int(float(row.get("price", "0")))
            except (ValueError, TypeError):
                continue  # unparseable price → skip
            if price <= 0 or price > _MAX_VALID_PRICE:
                continue  # abnormal value → skip

            # --- size: float ---
            try:
                size = float(row.get("size", "0"))
            except (ValueError, TypeError):
                size = 0.0

            # --- pet_friendly: bool ---
            pet_str = (row.get("pet_friendly", "False") or "False").strip()
            pet_friendly = pet_str.lower() in ("true", "1", "yes")
            # Augment with keyword detection from title / description
            title = (row.get("title") or "").strip()
            description = (row.get("description") or "").strip()
            if not pet_friendly and _looks_pet_friendly(title, description):
                pet_friendly = True

            properties.append(
                {
                    "id": (row.get("id") or "").strip(),
                    "title": title,
                    "location": (row.get("location") or "").strip(),
                    "price": price,
                    "size": size,
                    "bedrooms": (row.get("bedrooms") or "").strip(),
                    "pet_friendly": pet_friendly,
                    "description": description,
                }
            )

    return properties


# Global in-memory database (loaded once at import time)
PROPERTIES_DB: list[dict] = _load_properties(CSV_PATH)
import sys
print(f"[INFO] Loaded {len(PROPERTIES_DB)} properties from {os.path.basename(CSV_PATH)}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Tool: search_properties
# ---------------------------------------------------------------------------
@mcp.tool()
def search_properties(
    location: str,
    max_budget: int,
    pet_friendly: bool = False,
) -> list[dict]:
    """Search for rental properties matching the given criteria.

    Parameters
    ----------
    location : str
        District or area keyword. Matches against both the ``location``
        and ``title`` fields (case-insensitive substring match).
    max_budget : int
        Maximum monthly rent in CNY.
    pet_friendly : bool
        If True, only return properties that allow pets (default False).

    Returns
    -------
    list[dict]
        Up to 5 best-matching property listings.
    """
    results: list[dict] = []
    location_lower = (location or "").lower()

    for prop in PROPERTIES_DB:
        # --- Location filter ---
        if location_lower:
            loc_match = location_lower in (prop["location"] or "").lower()
            title_match = location_lower in (prop["title"] or "").lower()
            if not loc_match and not title_match:
                continue

        # --- Budget filter ---
        if prop["price"] > max_budget:
            continue

        # --- Pet-friendly filter (only when user asks for it) ---
        if pet_friendly and not prop["pet_friendly"]:
            continue

        results.append(prop)

    # Return top 5 (already in CSV order; stable)
    return results[:5]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
