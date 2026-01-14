"""Browser tool for LizCode - headless browser with raw HTML DOM."""

from __future__ import annotations

from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class BrowserTool(Tool):
    """Headless browser that returns raw HTML DOM."""

    name = "browser"
    description = """Headless browser for web interaction. Returns raw HTML DOM.

Actions:
- goto: Navigate to URL, return page HTML
- click: Click element by CSS selector
- type: Type text into element by CSS selector
- get_html: Get current page HTML
- execute_js: Run JavaScript and return result
- back: Go back in history
- forward: Go forward in history
- close: Close the browser

The browser returns raw HTML - you can read the DOM directly.
Use CSS selectors for click/type (e.g., "#login-button", "input[name=email]")."""

    permission = Permission.WRITE  # Can interact with web pages

    def __init__(self):
        self._browser = None
        self._page = None
        self._playwright = None

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["goto", "click", "type", "get_html", "execute_js", "back", "forward", "close"],
                    "description": "Browser action to perform",
                },
                "url": {
                    "type": "string",
                    "description": "URL to navigate to (for 'goto' action)",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector for element (for 'click' and 'type' actions)",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type (for 'type' action)",
                },
                "script": {
                    "type": "string",
                    "description": "JavaScript to execute (for 'execute_js' action)",
                },
            },
            "required": ["action"],
        }

    async def _ensure_browser(self) -> None:
        """Ensure browser is started."""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                raise RuntimeError(
                    "Playwright not installed. Run: pip install playwright && playwright install chromium"
                )

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._page = await self._browser.new_page()

    async def _get_html(self) -> str:
        """Get current page HTML."""
        if not self._page:
            return "<html><body>No page loaded</body></html>"

        content = await self._page.content()

        # Truncate if too large
        max_size = 150_000
        if len(content) > max_size:
            content = content[:max_size] + "\n<!-- HTML truncated - showing first 150KB -->"

        return content

    async def execute(
        self,
        action: str,
        url: str | None = None,
        selector: str | None = None,
        text: str | None = None,
        script: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute browser action."""
        try:
            if action == "goto":
                if not url:
                    return ToolResult(
                        success=False,
                        output="",
                        error="URL required for 'goto' action",
                    )

                await self._ensure_browser()
                await self._page.goto(url, wait_until="domcontentloaded")
                html = await self._get_html()

                return ToolResult(
                    success=True,
                    output=f"Navigated to: {self._page.url}\n\n{html}",
                )

            elif action == "click":
                if not selector:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Selector required for 'click' action",
                    )

                if not self._page:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No page loaded. Use 'goto' first.",
                    )

                await self._page.click(selector)
                await self._page.wait_for_load_state("domcontentloaded")
                html = await self._get_html()

                return ToolResult(
                    success=True,
                    output=f"Clicked: {selector}\nURL: {self._page.url}\n\n{html}",
                )

            elif action == "type":
                if not selector:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Selector required for 'type' action",
                    )
                if text is None:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Text required for 'type' action",
                    )

                if not self._page:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No page loaded. Use 'goto' first.",
                    )

                await self._page.fill(selector, text)
                html = await self._get_html()

                return ToolResult(
                    success=True,
                    output=f"Typed into: {selector}\n\n{html}",
                )

            elif action == "get_html":
                if not self._page:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No page loaded. Use 'goto' first.",
                    )

                html = await self._get_html()
                return ToolResult(
                    success=True,
                    output=f"URL: {self._page.url}\n\n{html}",
                )

            elif action == "execute_js":
                if not script:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Script required for 'execute_js' action",
                    )

                if not self._page:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No page loaded. Use 'goto' first.",
                    )

                result = await self._page.evaluate(script)
                return ToolResult(
                    success=True,
                    output=f"Result: {result}",
                )

            elif action == "back":
                if not self._page:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No page loaded.",
                    )

                await self._page.go_back()
                html = await self._get_html()
                return ToolResult(
                    success=True,
                    output=f"Navigated back to: {self._page.url}\n\n{html}",
                )

            elif action == "forward":
                if not self._page:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No page loaded.",
                    )

                await self._page.go_forward()
                html = await self._get_html()
                return ToolResult(
                    success=True,
                    output=f"Navigated forward to: {self._page.url}\n\n{html}",
                )

            elif action == "close":
                if self._browser:
                    await self._browser.close()
                    self._browser = None
                    self._page = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None

                return ToolResult(
                    success=True,
                    output="Browser closed.",
                )

            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown action: {action}",
                )

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Browser error: {e}",
            )

    async def close(self) -> None:
        """Clean up browser resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
