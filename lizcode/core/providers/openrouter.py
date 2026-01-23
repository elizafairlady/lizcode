"""OpenRouter provider for LizCode."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, AsyncIterator

import httpx

from lizcode.core.providers.base import Provider

if TYPE_CHECKING:
    from lizcode.tools.base import Tool


class OpenRouterProvider(Provider):
    """OpenRouter API provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-sonnet-4",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        super().__init__(model)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "openrouter"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/vii/lizcode",
                    "X-Title": "LizCode",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Send a chat completion request."""
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = self.format_tools(tools)
            payload["tool_choice"] = "auto"

        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Try to get error details from response body
            try:
                error_body = e.response.json()
                error_msg = error_body.get("error", {}).get("message", e.response.text[:500])
            except Exception:
                error_msg = e.response.text[:500] if e.response.text else str(e)
            
            raise RuntimeError(
                f"OpenRouter API error {e.response.status_code}: {error_msg}\n"
                f"Model: {self.model}, Messages: {len(messages)}, "
                f"Tools: {len(tools) if tools else 0}"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(
                f"Network error connecting to OpenRouter: {e}\n"
                f"Model: {self.model}"
            ) from e

        # Handle empty or invalid JSON responses
        response_text = response.text
        if not response_text or not response_text.strip():
            raise RuntimeError(
                f"Empty response from OpenRouter API.\n"
                f"This may be due to rate limiting or a temporary issue. "
                f"Model: {self.model}, Status: {response.status_code}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            # Check if it looks like HTML (error page)
            if response_text.strip().startswith("<"):
                raise RuntimeError(
                    f"OpenRouter returned HTML instead of JSON (possibly an error page).\n"
                    f"Status: {response.status_code}, First 200 chars: {response_text[:200]}"
                ) from e
            raise RuntimeError(
                f"Invalid JSON from OpenRouter: {e}\n"
                f"Response: {response_text[:500]}"
            ) from e
        choice = data["choices"][0]
        message = choice["message"]

        result: dict[str, Any] = {
            "content": message.get("content", ""),
            "finish_reason": choice.get("finish_reason"),
        }

        if message.get("tool_calls"):
            result["tool_calls"] = [
                {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"]),
                }
                for tc in message["tool_calls"]
            ]

        return result

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
    ) -> AsyncIterator[str]:
        """Stream a chat completion response."""
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        if tools:
            payload["tools"] = self.format_tools(tools)
            payload["tool_choice"] = "auto"

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue

                data = line[6:]  # Remove "data: " prefix
                if data == "[DONE]":
                    break

                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})

                    if content := delta.get("content"):
                        yield content
                except json.JSONDecodeError:
                    continue

    async def list_models(self) -> list[str]:
        """List available models from OpenRouter."""
        client = await self._get_client()
        try:
            response = await client.get("/models")
            response.raise_for_status()
            data = response.json()
            return [model["id"] for model in data.get("data", [])]
        except Exception:
            # Return empty list on error, don't break CLI
            return []
