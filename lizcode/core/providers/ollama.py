"""Ollama provider for LizCode."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, AsyncIterator

import httpx

from lizcode.core.providers.base import Provider

if TYPE_CHECKING:
    from lizcode.tools.base import Tool


class OllamaProvider(Provider):
    """Ollama local model provider."""

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
    ):
        super().__init__(model)
        self.host = host.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "ollama"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.host,
                headers={"Content-Type": "application/json"},
                timeout=300.0,  # Longer timeout for local models
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _format_tools_ollama(self, tools: list[Tool]) -> list[dict[str, Any]]:
        """Format tools for Ollama's tool calling format."""
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

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Send a chat completion request."""
        client = await self._get_client()

        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_msg = {
                "role": msg["role"],
                "content": msg.get("content", ""),
            }
            # Handle tool results
            if msg["role"] == "tool":
                ollama_msg["role"] = "tool"
                ollama_msg["content"] = msg.get("content", "")
            ollama_messages.append(ollama_msg)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
        }

        if tools:
            payload["tools"] = self._format_tools_ollama(tools)

        response = await client.post("/api/chat", json=payload)
        response.raise_for_status()

        data = response.json()
        message = data.get("message", {})

        result: dict[str, Any] = {
            "content": message.get("content", ""),
            "finish_reason": "stop",
        }

        # Handle tool calls from Ollama
        if message.get("tool_calls"):
            result["tool_calls"] = [
                {
                    "id": f"call_{i}",
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"]
                    if isinstance(tc["function"]["arguments"], dict)
                    else json.loads(tc["function"]["arguments"]),
                }
                for i, tc in enumerate(message["tool_calls"])
            ]

        return result

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
    ) -> AsyncIterator[str]:
        """Stream a chat completion response."""
        client = await self._get_client()

        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_msg = {
                "role": msg["role"],
                "content": msg.get("content", ""),
            }
            if msg["role"] == "tool":
                ollama_msg["role"] = "tool"
            ollama_messages.append(ollama_msg)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
        }

        if tools:
            payload["tools"] = self._format_tools_ollama(tools)

        async with client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                try:
                    chunk = json.loads(line)
                    if content := chunk.get("message", {}).get("content"):
                        yield content
                except json.JSONDecodeError:
                    continue

    async def list_models(self) -> list[str]:
        """List available models on the Ollama server."""
        client = await self._get_client()
        response = await client.get("/api/tags")
        response.raise_for_status()

        data = response.json()
        return [model["name"] for model in data.get("models", [])]

    async def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False
