"""Core components for LizCode."""

from lizcode.core.state import ConversationState, Message, Mode

__all__ = ["Agent", "ConversationState", "Message", "Mode"]


def __getattr__(name: str):
    """Lazy import Agent to avoid circular imports."""
    if name == "Agent":
        from lizcode.core.agent import Agent
        return Agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
