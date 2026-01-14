"""List files tool for LizCode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class ListFilesTool(Tool):
    """List files and directories."""

    name = "list_files"
    description = """List files and directories in a given path.

Usage:
- Lists contents of a directory
- Can list recursively for full directory trees
- Shows file sizes and indicates directories with /
- Useful for exploring project structure"""

    permission = Permission.READ

    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to list (default: current directory)",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List files recursively (default: false)",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files starting with . (default: false)",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        directory: str | None = None,
        recursive: bool = False,
        show_hidden: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """List files in a directory."""
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
            entries = []

            if recursive:
                iterator = base_dir.rglob("*")
            else:
                iterator = base_dir.iterdir()

            for path in sorted(iterator):
                # Skip hidden files unless requested
                if not show_hidden and path.name.startswith("."):
                    continue

                # Format entry
                try:
                    rel_path = path.relative_to(base_dir)
                    if path.is_dir():
                        entries.append(f"{rel_path}/")
                    else:
                        size = path.stat().st_size
                        size_str = self._format_size(size)
                        entries.append(f"{rel_path} ({size_str})")
                except (PermissionError, OSError):
                    continue

                if len(entries) >= self.max_entries:
                    break

            if not entries:
                return ToolResult(
                    success=True,
                    output=f"Directory is empty: {base_dir}",
                )

            output = "\n".join(entries)

            if len(entries) >= self.max_entries:
                output += f"\n\n[Showing {self.max_entries} entries, more may exist]"

            return ToolResult(
                success=True,
                output=output,
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {directory}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error listing directory: {e}",
            )

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
