"""Planning tools for LizCode - Plan mode only."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from lizcode.core.plan import Plan, PlanPhase
from lizcode.tools.base import Permission, Tool, ToolResult

if TYPE_CHECKING:
    from lizcode.core.state import ConversationState


class CreatePlanTool(Tool):
    """Create a new plan for implementation (Plan mode only)."""

    name = "create_plan"
    description = """Create a new plan for the implementation task.

Use this tool at the START of plan mode to define what you're planning.
This creates a structured plan that you'll build upon with update_plan.

When to use:
- Starting a new implementation task
- Resetting/replacing an existing plan
- Defining a clear objective for your exploration

The plan will be persisted to .lizcode/plan.md for reference."""

    permission = Permission.PLAN  # Only available in Plan mode

    def __init__(self, state: Any = None, working_dir: Path | None = None):
        self._state = state
        self._working_dir = working_dir or Path.cwd()

    def set_state(self, state: Any) -> None:
        """Set the conversation state."""
        self._state = state

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the plan (e.g., 'Add user authentication')",
                },
                "objective": {
                    "type": "string",
                    "description": "What needs to be accomplished",
                },
            },
            "required": ["title", "objective"],
        }

    async def execute(
        self,
        title: str,
        objective: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Create a new plan."""
        if not self._state:
            return ToolResult(
                success=False,
                output="",
                error="State not initialized",
            )

        # Clear any existing tasks from previous plans to avoid conflicts
        if hasattr(self._state, 'task_list') and self._state.task_list:
            self._state.task_list.clear_all()

        # Create the plan directory and file
        plan_dir = self._working_dir / ".lizcode"
        plan_dir.mkdir(parents=True, exist_ok=True)

        plan_path = plan_dir / "plan"
        plan = Plan.create(title, objective, plan_path)

        # Store plan reference in state (does NOT change mode)
        self._state.current_plan = plan

        return ToolResult(
            success=True,
            output=f"""Created plan: {title}

Objective: {objective}
Plan file: {plan_path}.md

Next steps:
1. Explore the codebase with read_file, grep, glob, list_files
2. Document findings with update_plan (add_context, add_step, etc.)
3. When complete, use finalize_plan to mark ready for implementation""",
        )


class UpdatePlanTool(Tool):
    """Update the current plan with new information (Plan mode only)."""

    name = "update_plan"
    description = """Update the current plan with new information.

Use during plan mode to build your implementation plan:
- add_context: Add findings from exploration
- add_step: Add an implementation step
- add_file: Mark a critical file
- add_verification: Add how to verify success
- set_approach: Define your chosen approach
- add_risk: Document potential risks

Requires an active plan (use create_plan first)."""

    permission = Permission.PLAN  # Only available in Plan mode

    def __init__(self, state: Any = None):
        self._state = state

    def set_state(self, state: Any) -> None:
        """Set the conversation state."""
        self._state = state

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add_context", "add_step", "add_file", "add_verification", "set_approach", "add_risk"],
                    "description": "What to update in the plan",
                },
                "content": {
                    "type": "string",
                    "description": "The content to add",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files involved (for add_step)",
                },
                "rationale": {
                    "type": "string",
                    "description": "Rationale for chosen approach (for set_approach)",
                },
            },
            "required": ["action", "content"],
        }

    async def execute(
        self,
        action: str,
        content: str,
        files: list[str] | None = None,
        rationale: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Update the plan."""
        if not self._state:
            return ToolResult(
                success=False,
                output="",
                error="State not initialized",
            )

        plan = getattr(self._state, 'current_plan', None)
        if not plan:
            return ToolResult(
                success=False,
                output="",
                error="No active plan. Use create_plan first.",
            )

        try:
            if action == "add_context":
                plan.add_context(content)
                return ToolResult(success=True, output=f"Added context: {content}")

            elif action == "add_step":
                from lizcode.core.plan import PlanStep
                step = PlanStep(
                    description=content,
                    files_involved=files or [],
                )
                plan.add_step(step)
                return ToolResult(success=True, output=f"Added step: {content}")

            elif action == "add_file":
                plan.add_critical_file(content)
                return ToolResult(success=True, output=f"Added critical file: {content}")

            elif action == "add_verification":
                plan.add_verification(content)
                return ToolResult(success=True, output=f"Added verification: {content}")

            elif action == "set_approach":
                plan.set_approach(content, rationale or "")
                return ToolResult(success=True, output=f"Set approach: {content}")

            elif action == "add_risk":
                plan.add_risk(content)
                return ToolResult(success=True, output=f"Added risk: {content}")

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
                error=f"Failed to update plan: {e}",
            )


class FinalizePlanTool(Tool):
    """Finalize the plan for implementation (Plan mode only)."""

    name = "finalize_plan"
    description = """Mark the plan as complete and ready for implementation.

Use this when you have:
1. Gathered enough context about the codebase
2. Designed an implementation approach
3. Documented the steps in your plan

This marks the plan as ready. The user will then switch to Act mode
with /act to begin implementation.

ALWAYS call this when done planning."""

    permission = Permission.PLAN  # Only available in Plan mode

    def __init__(self, state: Any = None):
        self._state = state

    def set_state(self, state: Any) -> None:
        """Set the conversation state."""
        self._state = state

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the plan for the user",
                },
                "ready_to_implement": {
                    "type": "boolean",
                    "description": "True if plan is complete and ready for implementation",
                },
            },
            "required": ["summary"],
        }

    async def execute(
        self,
        summary: str,
        ready_to_implement: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Finalize the plan."""
        if not self._state:
            return ToolResult(
                success=False,
                output="",
                error="State not initialized",
            )

        plan = getattr(self._state, 'current_plan', None)

        output_parts = [
            "## Plan Summary",
            "",
            summary,
            "",
        ]

        if plan:
            # Update plan phase
            plan.phase = PlanPhase.READY_TO_EXECUTE if ready_to_implement else PlanPhase.REVIEW
            plan._persist()

            output_parts.append(f"Plan file: {plan._persist_path}.md")
            output_parts.append("")

            if plan.steps:
                output_parts.append("## Implementation Steps")
                for i, step in enumerate(plan.steps, 1):
                    output_parts.append(f"{i}. {step.description}")
                output_parts.append("")

            if plan.verification_steps:
                output_parts.append("## Verification")
                for v in plan.verification_steps:
                    output_parts.append(f"- {v}")
                output_parts.append("")

        if ready_to_implement:
            output_parts.append("Plan is ready. User can approve with /act to begin implementation.")
        else:
            output_parts.append("Plan needs more work or user input.")

        return ToolResult(
            success=True,
            output="\n".join(output_parts),
        )
