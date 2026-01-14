"""Grep content search tool for LizCode."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class GrepTool(Tool):
    """Search file contents using regex."""

    name = "grep"
    description = """Search for patterns in file contents using regex.

Usage:
- Provide a regex pattern to search for
- Optionally specify a file pattern to filter which files to search
- Results include file paths, line numbers, and matching lines
- Context lines can be included around matches

Examples:
- Search for "def main" in Python files
- Search for "TODO" or "FIXME" comments
- Find function definitions matching a pattern"""

    permission = Permission.READ

    def __init__(self, max_results: int = 200, context_lines: int = 2):
        self.max_results = max_results
        self.context_lines = context_lines

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., **/*.py)",
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Ignore case when matching (default: false)",
                },
                "context": {
                    "type": "integer",
                    "description": f"Number of context lines around matches (default: {self.context_lines})",
                },
            },
            "required": ["pattern"],
        }

    async def execute(
        self,
        pattern: str,
        directory: str | None = None,
        file_pattern: str = "**/*",
        case_insensitive: bool = False,
        context: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Search file contents for a pattern."""
        base_dir = Path(directory).expanduser().resolve() if directory else Path.cwd()
        context = context if context is not None else self.context_lines

        if not base_dir.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Directory not found: {directory}",
            )

        try:
            flags = re.IGNORECASE if case_insensitive else 0
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid regex pattern: {e}",
            )

        try:
            matches = []
            files_searched = 0
            files_with_matches = 0

            for file_path in base_dir.glob(file_pattern):
                if not file_path.is_file():
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    files_searched += 1

                    file_matches = []
                    for i, line in enumerate(lines):
                        if regex.search(line):
                            # Get context lines
                            start = max(0, i - context)
                            end = min(len(lines), i + context + 1)

                            context_block = []
                            for j in range(start, end):
                                prefix = ">" if j == i else " "
                                context_block.append(f"{prefix} {j + 1:4}: {lines[j]}")

                            file_matches.append("\n".join(context_block))

                    if file_matches:
                        files_with_matches += 1
                        matches.append(f"--- {file_path} ---\n" + "\n...\n".join(file_matches))

                        if len(matches) >= self.max_results:
                            break

                except (UnicodeDecodeError, PermissionError):
                    continue

            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No matches found for pattern: {pattern}\n(Searched {files_searched} files)",
                )

            output = "\n\n".join(matches)
            output += f"\n\n[Found matches in {files_with_matches} files, searched {files_searched} files]"

            if len(matches) >= self.max_results:
                output += f"\n[Results limited to {self.max_results} files]"

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
