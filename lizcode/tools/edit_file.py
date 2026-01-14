"""Edit file tool for LizCode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class EditFileTool(Tool):
    """Edit a file using search and replace."""

    name = "edit_file"
    description = """Edit a file by replacing specific text.

Usage:
- You must read the file first before editing
- Provide the exact text to search for (old_string)
- Provide the replacement text (new_string)
- The old_string must be unique in the file, or use replace_all=true
- Preserve exact indentation when editing

Tips:
- Include enough context to make old_string unique
- For multiple edits, make separate calls in order of appearance"""

    permission = Permission.WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to edit",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact text to find and replace",
                },
                "new_string": {
                    "type": "string",
                    "description": "The text to replace old_string with",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences instead of just the first (default: false)",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    async def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Edit a file using search and replace."""
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
            content = path.read_text(encoding="utf-8")

            # Check if old_string exists
            count = content.count(old_string)
            if count == 0:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Could not find the specified text in {file_path}",
                )

            # Check for uniqueness if not replace_all
            if not replace_all and count > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Found {count} occurrences of the text. Use replace_all=true or provide more context to make it unique.",
                )

            # Perform the replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replaced_count = count
            else:
                new_content = content.replace(old_string, new_string, 1)
                replaced_count = 1

            # Write the updated content
            path.write_text(new_content, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"Edited {file_path} ({replaced_count} replacement{'s' if replaced_count > 1 else ''})",
            )

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error=f"Cannot edit file as text (binary file?): {file_path}",
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
                error=f"Error editing file: {e}",
            )
