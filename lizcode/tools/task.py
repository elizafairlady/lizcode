"""Task tool for LizCode - spawns specialized subagents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lizcode.core.subagent import SubagentType
from lizcode.tools.base import Permission, Tool, ToolResult

if TYPE_CHECKING:
    from lizcode.core.subagent import SubagentManager


class TaskTool(Tool):
    """Launch specialized subagents to handle complex tasks autonomously."""

    name = "task"
    description = """Launch a new agent to handle complex, multi-step tasks autonomously.

Available agent types:
- explore: Codebase exploration (read files, search, understand structure)
- plan: Design implementation approaches (analyze, plan, suggest)
- test_runner: Run tests and report results
- build_validator: Validate builds succeed
- code_reviewer: Review code for issues

When to use:
- Complex exploration that requires multiple file reads
- Design work that benefits from focused analysis
- Running tests after code changes
- Validating builds

When NOT to use:
- Reading a specific file (use read_file directly)
- Searching for a specific pattern (use grep directly)
- Simple single-file operations

Usage:
- Launch multiple agents concurrently when tasks are independent
- For long-running tasks, use run_in_background=true
- Provide clear, detailed prompts for best results
- Agent results are returned to you, summarize for user"""

    permission = Permission.READ  # Subagents have their own permissions

    def __init__(self, subagent_manager: Any | None = None):
        self._manager = subagent_manager

    def set_manager(self, manager: Any) -> None:
        """Set the subagent manager."""
        self._manager = manager

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subagent_type": {
                    "type": "string",
                    "enum": ["explore", "plan", "test_runner", "build_validator", "code_reviewer"],
                    "description": "Type of specialized agent to launch",
                },
                "prompt": {
                    "type": "string",
                    "description": "Detailed task description for the agent",
                },
                "description": {
                    "type": "string",
                    "description": "Short 3-5 word summary of what agent will do",
                },
                "run_in_background": {
                    "type": "boolean",
                    "description": "If true, agent runs in background and returns output file path",
                },
                "resume": {
                    "type": "string",
                    "description": "Agent ID to resume from a previous invocation",
                },
            },
            "required": ["subagent_type", "prompt"],
        }

    async def execute(
        self,
        subagent_type: str,
        prompt: str,
        description: str = "",
        run_in_background: bool = False,
        resume: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Launch a subagent."""
        if not self._manager:
            return ToolResult(
                success=False,
                output="",
                error="Subagent manager not initialized",
            )

        try:
            agent_type = SubagentType(subagent_type)
        except ValueError:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown agent type: {subagent_type}. Use: explore, plan, test_runner, build_validator, code_reviewer",
            )

        try:
            # Handle resume
            if resume:
                prompt = self._manager.resume_agent(resume, prompt)

            # Spawn the agent
            result = await self._manager.spawn(
                agent_type=agent_type,
                prompt=prompt,
                run_in_background=run_in_background,
            )

            if not result.success:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.error or "Agent failed",
                )

            # Format output
            output_parts = [
                f"Agent: {result.agent_type.value} ({result.agent_id})",
            ]

            if run_in_background:
                output_parts.append(f"Status: Running in background")
                output_parts.append(f"Output file: {result.output_file}")
                output_parts.append("Use read_file on the output file to check progress.")
            else:
                output_parts.append(f"Duration: {result.duration_seconds:.1f}s")
                output_parts.append("")
                output_parts.append("Result:")
                output_parts.append(result.result)

            return ToolResult(
                success=True,
                output="\n".join(output_parts),
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to spawn agent: {e}",
            )


class AskUserQuestionTool(Tool):
    """Ask the user a clarifying question."""

    name = "ask_user"
    description = """Ask the user a clarifying question when you need more information.

Use when:
- Requirements are ambiguous
- Multiple valid approaches exist and user preference matters
- You need to confirm understanding before proceeding
- Making assumptions that could lead to wasted work

Provide clear, specific questions. Avoid vague questions.
Include options when applicable to make it easy for user to respond.

This tool will prompt the user interactively and return their response."""

    permission = Permission.READ

    def __init__(self, question_callback: Any | None = None):
        self._callback = question_callback

    def set_callback(self, callback: Any) -> None:
        """Set the callback for asking questions.
        
        Callback signature: async def callback(question: str, options: list[str] | None, context: str | None) -> str
        """
        self._callback = callback

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of choices to present",
                },
                "context": {
                    "type": "string",
                    "description": "Brief context for why you're asking",
                },
            },
            "required": ["question"],
        }

    async def execute(
        self,
        question: str,
        options: list[str] | None = None,
        context: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Ask the user a question and return their response."""
        # If callback is set, use it to prompt user interactively
        if self._callback:
            try:
                user_response = await self._callback(question, options, context)
                return ToolResult(
                    success=True,
                    output=f"User response: {user_response}",
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to get user input: {e}",
                )
        
        # Fallback: format question as output (not interactive)
        output_parts = []

        if context:
            output_parts.append(f"Context: {context}")
            output_parts.append("")

        output_parts.append(f"Question: {question}")

        if options:
            output_parts.append("")
            output_parts.append("Options:")
            for i, opt in enumerate(options, 1):
                output_parts.append(f"  {i}. {opt}")
        
        output_parts.append("")
        output_parts.append("[No interactive callback - question displayed but no response collected]")

        return ToolResult(
            success=True,
            output="\n".join(output_parts),
        )
