"""WebFetch tool for LizCode - fetch and analyze web content."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from lizcode.tools.base import Permission, Tool, ToolResult


class WebFetchTool(Tool):
    """Fetch content from a URL and convert to readable format."""

    name = "webfetch"
    description = """Fetch content from a URL and return it.

Use this to:
- Read documentation
- Fetch API responses
- Get web page content

The URL must be a fully-formed valid URL.
HTTP URLs will be automatically upgraded to HTTPS.
Returns HTML content (or JSON for API endpoints)."""

    permission = Permission.READ

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "LizCode/1.0 (AI pair programming assistant)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
        return self._client

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                },
            },
            "required": ["url"],
        }

    async def execute(
        self,
        url: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Fetch content from URL."""
        # Validate and normalize URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Upgrade HTTP to HTTPS
        if url.startswith("http://"):
            url = "https://" + url[7:]

        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid URL: {url}",
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid URL: {e}",
            )

        try:
            client = await self._get_client()
            response = await client.get(url)

            content_type = response.headers.get("content-type", "")

            # Check if it's JSON
            if "application/json" in content_type:
                return ToolResult(
                    success=True,
                    output=response.text,
                )

            # Return HTML content
            content = response.text

            # Truncate if too large (keep first 100KB)
            max_size = 100_000
            if len(content) > max_size:
                content = content[:max_size] + "\n\n[Content truncated - showing first 100KB]"

            return ToolResult(
                success=True,
                output=f"URL: {response.url}\nStatus: {response.status_code}\n\n{content}",
            )

        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                output="",
                error=f"Request timed out after {self.timeout}s",
            )
        except httpx.RequestError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Request failed: {e}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error fetching URL: {e}",
            )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
