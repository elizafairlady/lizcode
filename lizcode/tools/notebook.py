"""Notebook editing tool for LizCode - Jupyter notebook support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class NotebookEditTool(Tool):
    """Edit Jupyter notebook cells."""

    name = "notebook_edit"
    description = """Edit Jupyter notebook (.ipynb) cells.

Actions:
- read: Read all cells from a notebook
- edit: Replace contents of a specific cell
- insert: Insert a new cell at a position
- delete: Delete a cell at a position

Cell numbers are 0-indexed.
Cell types: "code" or "markdown"."""

    permission = Permission.WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "edit", "insert", "delete"],
                    "description": "Action to perform",
                },
                "notebook_path": {
                    "type": "string",
                    "description": "Absolute path to the .ipynb file",
                },
                "cell_number": {
                    "type": "integer",
                    "description": "0-indexed cell number (for edit/insert/delete)",
                },
                "source": {
                    "type": "string",
                    "description": "Cell content (for edit/insert)",
                },
                "cell_type": {
                    "type": "string",
                    "enum": ["code", "markdown"],
                    "description": "Cell type (for insert, default: code)",
                },
            },
            "required": ["action", "notebook_path"],
        }

    async def execute(
        self,
        action: str,
        notebook_path: str,
        cell_number: int | None = None,
        source: str | None = None,
        cell_type: str = "code",
        **kwargs: Any,
    ) -> ToolResult:
        """Execute notebook operation."""
        path = Path(notebook_path).expanduser().resolve()

        if not path.suffix == ".ipynb":
            return ToolResult(
                success=False,
                output="",
                error=f"Not a notebook file: {notebook_path}",
            )

        try:
            if action == "read":
                if not path.exists():
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Notebook not found: {notebook_path}",
                    )

                notebook = json.loads(path.read_text(encoding="utf-8"))
                cells = notebook.get("cells", [])

                output_parts = [f"Notebook: {notebook_path}", f"Cells: {len(cells)}", ""]

                for i, cell in enumerate(cells):
                    ct = cell.get("cell_type", "unknown")
                    src = "".join(cell.get("source", []))
                    # Truncate long cells
                    if len(src) > 500:
                        src = src[:500] + "..."
                    output_parts.append(f"--- Cell {i} ({ct}) ---")
                    output_parts.append(src)
                    output_parts.append("")

                return ToolResult(
                    success=True,
                    output="\n".join(output_parts),
                )

            elif action == "edit":
                if cell_number is None:
                    return ToolResult(
                        success=False,
                        output="",
                        error="cell_number required for 'edit' action",
                    )
                if source is None:
                    return ToolResult(
                        success=False,
                        output="",
                        error="source required for 'edit' action",
                    )
                if not path.exists():
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Notebook not found: {notebook_path}",
                    )

                notebook = json.loads(path.read_text(encoding="utf-8"))
                cells = notebook.get("cells", [])

                if cell_number < 0 or cell_number >= len(cells):
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Cell {cell_number} out of range (0-{len(cells)-1})",
                    )

                # Update cell source
                cells[cell_number]["source"] = source.splitlines(keepends=True)

                path.write_text(json.dumps(notebook, indent=1), encoding="utf-8")

                return ToolResult(
                    success=True,
                    output=f"Updated cell {cell_number} in {notebook_path}",
                )

            elif action == "insert":
                if cell_number is None:
                    return ToolResult(
                        success=False,
                        output="",
                        error="cell_number required for 'insert' action",
                    )
                if source is None:
                    return ToolResult(
                        success=False,
                        output="",
                        error="source required for 'insert' action",
                    )

                if path.exists():
                    notebook = json.loads(path.read_text(encoding="utf-8"))
                else:
                    # Create new notebook
                    notebook = {
                        "cells": [],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }

                cells = notebook.get("cells", [])

                new_cell = {
                    "cell_type": cell_type,
                    "metadata": {},
                    "source": source.splitlines(keepends=True),
                }
                if cell_type == "code":
                    new_cell["execution_count"] = None
                    new_cell["outputs"] = []

                # Insert at position
                cell_number = max(0, min(cell_number, len(cells)))
                cells.insert(cell_number, new_cell)
                notebook["cells"] = cells

                path.write_text(json.dumps(notebook, indent=1), encoding="utf-8")

                return ToolResult(
                    success=True,
                    output=f"Inserted {cell_type} cell at position {cell_number}",
                )

            elif action == "delete":
                if cell_number is None:
                    return ToolResult(
                        success=False,
                        output="",
                        error="cell_number required for 'delete' action",
                    )
                if not path.exists():
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Notebook not found: {notebook_path}",
                    )

                notebook = json.loads(path.read_text(encoding="utf-8"))
                cells = notebook.get("cells", [])

                if cell_number < 0 or cell_number >= len(cells):
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Cell {cell_number} out of range (0-{len(cells)-1})",
                    )

                deleted = cells.pop(cell_number)
                notebook["cells"] = cells

                path.write_text(json.dumps(notebook, indent=1), encoding="utf-8")

                return ToolResult(
                    success=True,
                    output=f"Deleted cell {cell_number} ({deleted.get('cell_type', 'unknown')})",
                )

            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown action: {action}",
                )

        except json.JSONDecodeError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid notebook JSON: {e}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Notebook error: {e}",
            )
