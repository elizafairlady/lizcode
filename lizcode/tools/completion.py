"""Completion tool for LizCode - signals task completion."""

from __future__ import annotations

from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class AttemptCompletionTool(Tool):
    """Signal that the current task/request has been completed."""

    name = "attempt_completion"
    description = """Signal that you have completed the user's task.

Use this tool when you have:
1. Finished implementing the requested changes
2. Verified the changes work (ran tests, checked output, etc.)
3. Ready to summarize what was done

This tool:
- Marks the task as complete
- Provides a summary to the user
- Optionally suggests a command to verify the result

ALWAYS call this when done with a task. Don't leave the user hanging."""

    permission = Permission.WRITE  # ACT mode only - signals completion

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "A clear, concise summary (1-2 paragraphs) of what was accomplished",
                },
                "command": {
                    "type": "string",
                    "description": "Optional command the user can run to verify/review the result (e.g., 'python -m pytest', 'npm start')",
                },
            },
            "required": ["result"],
        }

    async def execute(
        self,
        result: str,
        command: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Mark task as complete and provide summary."""
        output_parts = [
            "## ✅ Task Complete",
            "",
            result,
        ]

        if command:
            output_parts.extend([
                "",
                "### Verify with:",
                f"```",
                command,
                f"```",
            ])

        return ToolResult(
            success=True,
            output="\n".join(output_parts),
        )
