"""
apps/mcp/policy.py — Who may connect an MCP client (``MCP_AUTH["CAN_CONNECT"]``).

Staff only to start with: an MCP client acts with the user's full access,
so widen this deliberately, as a product decision. It runs on the consent
page and on every call, so revoking staff status cuts a user's clients off.
Ported from the Titan template.
"""

from typing import Any


def staff_only(user: Any) -> bool:
    """Return whether ``user`` may connect: an active staff member may."""
    return bool(user.is_active and user.is_staff)
