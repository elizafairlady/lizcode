"""Read file tool for LizCode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class ReadFileTool(Tool):
    """Read contents of a file."""

    name = "read_file"
    description = """Read the contents of a file from the filesystem.

Usage:
- Provide an absolute path to the file
- By default reads up to 2000 lines from the beginning
- Can specify line offset and limit for large files
- Results include line numbers for reference
- Can read text files, code, configs, etc."""

    permission = Permission.READ

    def __init__(self, default_lines: int = 2000, max_line_length: int = 500):
        self.default_lines = default_lines
        self.max_line_length = max_line_length

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-indexed, default: 0)",
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of lines to read (default: {self.default_lines})",
                },
            },
            "required": ["file_path"],
        }

    async def execute(
        self,
        file_path: str,
        offset: int = 0,
        limit: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Read a file's contents."""
        limit = limit or self.default_lines
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"File not found: {file_path}",
            )

        if path.is_dir():
            return ToolResult(
                success=False,
                output="",
                error=f"Path is a directory, not a file: {file_path}",
            )

        try:
            # Try to read as text
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            # Apply offset and limit
            total_lines = len(lines)
            selected_lines = lines[offset : offset + limit]

            # Format with line numbers
            output_lines = []
            for i, line in enumerate(selected_lines, start=offset + 1):
                # Truncate long lines
                if len(line) > self.max_line_length:
                    line = line[: self.max_line_length] + "..."
                output_lines.append(f"{i:6}\t{line}")

            output = "\n".join(output_lines)

            # Add info about truncation
            if offset > 0 or offset + limit < total_lines:
                output += f"\n\n[Showing lines {offset + 1}-{min(offset + limit, total_lines)} of {total_lines}]"

            return ToolResult(
                success=True,
                output=output or "(empty file)",
            )

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error=f"Cannot read file as text (binary file?): {file_path}",
            )
        except PermissionError:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {file_path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading file: {e}",
            )
