"""Plugin API v1.1.12 external-app context, distinct from host account context."""

from typing import Any
from uuid import UUID

API_CONTRACT_VERSION = "1.1.12"


def participant_context(values: dict[str, Any]) -> dict[str, Any]:
    """Use only the reserved context injected by the protected host transport."""
    context = values.get("_public_app_context")
    if not isinstance(context, dict) or not isinstance(context.get("room"), str):
        raise ValueError("A verified public-app participant is required.")
    UUID(str(context["actor_id"]))
    return context
