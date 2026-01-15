"""TodoWrite tool for LizCode - AI-facing task management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lizcode.core.state import Mode
from lizcode.tools.base import Permission, Tool, ToolResult

if TYPE_CHECKING:
    from lizcode.core.tasks import TaskList


class TodoWriteTool(Tool):
    """Create and manage a task list for the current session."""

    name = "todo_write"
    description = """Create and manage a structured task list for the current coding session.

Use this tool proactively when:
1. Complex multi-step tasks (3+ distinct steps)
2. User provides multiple tasks
3. After receiving new instructions - capture requirements as todos
4. When starting work - mark task as in_progress BEFORE beginning
5. After completing - mark as completed IMMEDIATELY

When NOT to use:
- Single, straightforward tasks
- Trivial tasks that can be done in <3 steps
- Purely conversational requests

Task states:
- pending: Not yet started
- in_progress: Currently working on (ONLY ONE at a time)
- completed: Finished successfully

IMPORTANT: Mark tasks completed IMMEDIATELY after finishing. Do not batch completions.
Only ONE task can be in_progress at any time."""

    permission = Permission.READ  # Available in both modes, but restricted in Plan mode

    def __init__(self, task_list: TaskList | None = None):
        self._task_list = task_list
        self._mode: Mode | None = None  # Set by agent

    def set_mode(self, mode: Mode) -> None:
        """Set current mode for action validation."""
        self._mode = mode

    def set_task_list(self, task_list: TaskList) -> None:
        """Set the task list to manage."""
        self._task_list = task_list

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "start", "complete", "remove", "list"],
                    "description": "Action to perform on the task list",
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Task description in imperative form (e.g., 'Run tests')",
                            },
                            "active_form": {
                                "type": "string",
                                "description": "Present continuous form (e.g., 'Running tests')",
                            },
                        },
                        "required": ["content", "active_form"],
                    },
                    "description": "Tasks to add (for 'create' action)",
                },
                "task_id": {
                    "type": "string",
                    "description": "Task ID (for 'start', 'complete', 'remove' actions)",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        tasks: list[dict[str, str]] | None = None,
        task_id: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a task list operation."""
        if not self._task_list:
            return ToolResult(
                success=False,
                output="",
                error="Task list not initialized",
            )

        # In Plan mode, only "list" action is allowed
        if self._mode == Mode.PLAN and action != "list":
            return ToolResult(
                success=False,
                output="",
                error=f"Action '{action}' not allowed in Plan mode. Only 'list' is available. Switch to Act mode to manage tasks.",
            )

        try:
            if action == "create":
                if not tasks:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No tasks provided for 'create' action",
                    )

                created = self._task_list.add_tasks(tasks)
                # Format: [id] [ ] content (consistent with to_display)
                task_lines = [f"[{t.id}] [ ] {t.content}" for t in created]
                return ToolResult(
                    success=True,
                    output="\n".join(task_lines),
                )

            elif action == "start":
                if not task_id:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No task_id provided for 'start' action",
                    )

                task = self._task_list.start_task(task_id)
                if not task:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Task not found: {task_id}",
                    )

                # Format: [id] [>] active_form (consistent with to_display)
                return ToolResult(
                    success=True,
                    output=f"[{task.id}] [>] {task.active_form}",
                )

            elif action == "complete":
                if not task_id:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No task_id provided for 'complete' action",
                    )

                task = self._task_list.complete_task(task_id)
                if not task:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Task not found: {task_id}",
                    )

                # Format: [id] [x] content + progress (consistent with to_display)
                progress = self._task_list.get_progress_display()
                return ToolResult(
                    success=True,
                    output=f"[{task.id}] [x] {task.content} {progress}",
                )

            elif action == "remove":
                if not task_id:
                    return ToolResult(
                        success=False,
                        output="",
                        error="No task_id provided for 'remove' action",
                    )

                # Need to get task before removing to show content
                task = self._task_list.get_task(task_id)
                if not task:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Task not found: {task_id}",
                    )
                
                content = task.content
                self._task_list.remove_task(task_id)

                # Format: [id] [-] content (consistent format)
                return ToolResult(
                    success=True,
                    output=f"[{task_id}] [-] {content}",
                )

            elif action == "list":
                # Full list only when explicitly requested
                return ToolResult(
                    success=True,
                    output=f"{self._task_list.get_progress_display()}\n{self._task_list.to_display()}",
                )

            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown action: {action}. Use: create, start, complete, remove, list",
                )

        except ValueError as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Task operation failed: {e}",
            )
