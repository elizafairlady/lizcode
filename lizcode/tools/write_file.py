"""Write file tool for LizCode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class WriteFileTool(Tool):
    """Write content to a file."""

    name = "write_file"
    description = """Write content to a file, creating it if it doesn't exist.

Usage:
- Provide an absolute path to the file
- Parent directories will be created if they don't exist
- If the file exists, it will be overwritten
- Prefer editing existing files over creating new ones"""

    permission = Permission.WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(
        self,
        file_path: str,
        content: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Write content to a file."""
        path = Path(file_path).expanduser().resolve()

        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file exists (for reporting)
            existed = path.exists()

            # Write the content
            path.write_text(content, encoding="utf-8")

            action = "Updated" if existed else "Created"
            lines = len(content.splitlines())

            return ToolResult(
                success=True,
                output=f"{action} {file_path} ({lines} lines)",
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
                error=f"Error writing file: {e}",
            )
