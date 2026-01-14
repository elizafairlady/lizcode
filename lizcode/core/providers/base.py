"""Base provider interface for LizCode."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterator

if TYPE_CHECKING:
    from lizcode.tools.base import Tool


class Provider(ABC):
    """Abstract base class for model providers."""

    def __init__(self, model: str | None = None):
        self.model = model

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Send a chat completion request.

        Args:
            messages: List of messages in API format
            tools: Optional list of available tools
            stream: Whether to stream the response

        Returns:
            Response dict with 'content' and optionally 'tool_calls'
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
    ) -> AsyncIterator[str]:
        """Stream a chat completion response.

        Args:
            messages: List of messages in API format
            tools: Optional list of available tools

        Yields:
            Content chunks as they arrive
        """
        ...

    def format_tools(self, tools: list[Tool]) -> list[dict[str, Any]]:
        """Format tools for the API request."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
