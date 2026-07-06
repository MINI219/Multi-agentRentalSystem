"""Agent definitions for the multi-agent rental system.

Supervisor-routing architecture:
    supervisor       — entry point, decides which agent to invoke next
    profile_agent    — converses with user to clarify rental requirements
    search_agent     — searches for matching rental properties
    recommendation_agent — evaluates and ranks candidate properties
"""
