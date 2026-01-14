"""Glob file search tool for LizCode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class GlobTool(Tool):
    """Find files matching a glob pattern."""

    name = "glob"
    description = """Find files matching a glob pattern.

Usage:
- Use glob patterns like *.py, **/*.js, src/**/*.ts
- ** matches any number of directories
- * matches any filename characters
- Results are sorted and limited to prevent overwhelming output

Examples:
- "*.py" - Python files in current directory
- "**/*.py" - Python files recursively
- "src/**/*.ts" - TypeScript files under src/
- "**/test_*.py" - Test files anywhere"""

    permission = Permission.READ

    def __init__(self, max_results: int = 500):
        self.max_results = max_results

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., **/*.py)",
                },
                "directory": {
                    "type": "string",
                    "description": "Base directory to search in (default: current directory)",
                },
            },
            "required": ["pattern"],
        }

    async def execute(
        self,
        pattern: str,
        directory: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Find files matching a glob pattern."""
        base_dir = Path(directory).expanduser().resolve() if directory else Path.cwd()

        if not base_dir.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Directory not found: {directory}",
            )

        if not base_dir.is_dir():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a directory: {directory}",
            )

        try:
            # Find matching files
            matches = sorted(base_dir.glob(pattern))

            # Filter to only files (not directories)
            files = [str(p) for p in matches if p.is_file()]

            total_found = len(files)

            # Limit results
            if len(files) > self.max_results:
                files = files[: self.max_results]

            if not files:
                return ToolResult(
                    success=True,
                    output=f"No files found matching pattern: {pattern}",
                )

            output = "\n".join(files)

            if total_found > self.max_results:
                output += f"\n\n[Showing {self.max_results} of {total_found} matches]"

            return ToolResult(
                success=True,
                output=output,
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error searching files: {e}",
            )
