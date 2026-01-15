"""Main agent for LizCode."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable

from lizcode.core.plan import Plan
from lizcode.core.prompts import get_plan_context, get_system_prompt, get_task_context
from lizcode.core.state import ConversationState, Mode, Role, ToolCall
from lizcode.core.state import ToolResult as StateToolResult
from lizcode.core.subagent import SubagentManager
from lizcode.core.tasks import TaskList

if TYPE_CHECKING:
    from lizcode.core.providers.base import Provider
    from lizcode.tools.base import ToolRegistry


class Agent:
    """Main agent that manages conversations and tool execution."""

    def __init__(
        self,
        provider: Provider,
        state: ConversationState | None = None,
        tool_registry: ToolRegistry | None = None,
        approval_callback: Callable[[str, str, dict], bool] | None = None,
        question_callback: Callable[[str, list | None, str | None], str] | None = None,
        working_directory: Path | None = None,
    ):
        self.provider = provider
        self.state = state or ConversationState()
        self.working_directory = working_directory or Path.cwd()
        self.approval_callback = approval_callback or self._default_approval
        self.question_callback = question_callback

        # Initialize task list and plan
        lizcode_dir = self.working_directory / ".lizcode"
        lizcode_dir.mkdir(parents=True, exist_ok=True)

        self.task_list = TaskList.load(lizcode_dir / "tasks.json")
        self.current_plan: Plan | None = None

        # Create subagent manager
        def provider_factory():
            # Clone the provider settings
            if hasattr(provider, 'api_key'):
                from lizcode.core.providers.openrouter import OpenRouterProvider
                return OpenRouterProvider(
                    api_key=provider.api_key,
                    model=provider.model,
                    base_url=getattr(provider, 'base_url', 'https://openrouter.ai/api/v1'),
                )
            else:
                from lizcode.core.providers.ollama import OllamaProvider
                return OllamaProvider(
                    model=provider.model,
                    host=getattr(provider, 'host', 'http://localhost:11434'),
                )

        self.subagent_manager = SubagentManager(
            provider_factory=provider_factory,
            working_directory=self.working_directory,
        )

        # Create tool registry with wired tools
        self.tool_registry = self._create_wired_registry()

        # Set provider/model info in state
        self.state.provider = provider.name
        self.state.model = provider.model or ""
        self.state.working_directory = str(self.working_directory)

    def _create_wired_registry(self):
        """Create a tool registry with properly wired tools."""
        # Import here to avoid circular imports
        from lizcode.tools import create_tool_registry
        from lizcode.tools.todo_write import TodoWriteTool
        from lizcode.tools.task import TaskTool, AskUserQuestionTool
        from lizcode.tools.mode import CreatePlanTool, FinalizePlanTool, UpdatePlanTool
        
        registry = create_tool_registry()

        # Wire up tools that need state
        for tool in registry.get_all():
            if isinstance(tool, TodoWriteTool):
                tool.set_task_list(self.task_list)
            elif isinstance(tool, TaskTool):
                tool.set_manager(self.subagent_manager)
            elif isinstance(tool, AskUserQuestionTool):
                if self.question_callback:
                    tool.set_callback(self.question_callback)
            elif isinstance(tool, (CreatePlanTool, FinalizePlanTool, UpdatePlanTool)):
                tool.set_state(self)
                if isinstance(tool, CreatePlanTool):
                    tool._working_dir = self.working_directory

        return registry

    @staticmethod
    def _default_approval(tool_name: str, description: str, args: dict) -> bool:
        """Default approval callback - always returns True."""
        return True

    def _has_plan(self) -> bool:
        """Check if a plan exists in current session."""
        return self.current_plan is not None

    def get_available_tools(self) -> list:
        """Get tools available for the current mode and state context."""
        return self.tool_registry.get_for_context(self.state.mode, self._has_plan())

    def _build_messages(self) -> list[dict[str, Any]]:
        """Build the messages list for the API call."""
        messages = []

        # Get available tools for current context
        available_tools = self.get_available_tools()
        has_plan = self._has_plan()

        # Build system prompt with context AND available tools
        system_prompt = get_system_prompt(
            mode=self.state.mode,
            working_directory=str(self.working_directory),
            available_tools=available_tools,
            has_plan=has_plan,
        )

        # Add task context if tasks exist
        task_context = get_task_context(self.task_list)
        if task_context:
            system_prompt += task_context

        # Add plan context if plan exists
        plan_context = get_plan_context(self.current_plan)
        if plan_context:
            system_prompt += plan_context

        messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        for msg in self.state.messages:
            messages.append(msg.to_api_format())

        return messages

    async def chat(self, user_message: str) -> AsyncIterator[dict[str, Any]]:
        """Process a user message and yield response chunks.

        Yields dicts with:
        - {"type": "content", "text": str} for text content
        - {"type": "tool_call", "tool": str, "args": dict} for tool calls
        - {"type": "tool_result", "tool": str, "result": str, "success": bool} for results
        - {"type": "error", "message": str} for errors
        - {"type": "mode_change", "mode": str} for mode changes
        - {"type": "task_update", "tasks": str} for task list updates
        """
        # Add user message to state
        self.state.add_user_message(user_message)

        # Process in a loop to handle tool calls
        iterations = 0
        # Plan mode: unlimited iterations (exploration is unbounded)
        # Act mode: limit iterations but prompt user to continue
        max_iterations = None if self.state.mode == Mode.PLAN else 25
        iteration_warning_at = 20  # Warn at this point in act mode

        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            
            # In act mode, check if we should prompt user to continue
            if self.state.mode == Mode.ACT and iterations == iteration_warning_at:
                yield {
                    "type": "iteration_limit", 
                    "count": iterations,
                    "message": f"Reached {iterations} iterations. Continue execution?"
                }

            messages = self._build_messages()
            tools = self.get_available_tools()

            try:
                response = await self.provider.chat(messages, tools=tools if tools else None)
            except Exception as e:
                yield {"type": "error", "message": f"API error: {e}"}
                return

            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            # Yield any text content
            if content:
                yield {"type": "content", "text": content}

            # Handle tool calls
            if tool_calls:
                # Convert to our ToolCall format
                parsed_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc["arguments"],
                    )
                    for tc in tool_calls
                ]

                # Add assistant message with tool calls
                self.state.add_assistant_message(content, tool_calls=parsed_calls)

                # Execute each tool call
                for tc in parsed_calls:
                    yield {"type": "tool_call", "tool": tc.name, "args": tc.arguments}

                    result = await self._execute_tool(tc)

                    yield {
                        "type": "tool_result",
                        "tool": tc.name,
                        "result": result.result,
                        "success": result.success,
                    }

                    # Add tool result to state
                    self.state.add_tool_result(result)

                    # Mode changes are user-controlled via /plan and /act
                    # Tools do not switch modes anymore

                    # Check for task updates - emit only the changed row from tool result
                    if tc.name == "todo_write" and result.success:
                        yield {"type": "task_update", "tasks": result.result}

                # Continue the loop to get the next response
                continue

            # No tool calls - we're done
            if content:
                self.state.add_assistant_message(content)
            break

    async def _execute_tool(self, tool_call: ToolCall) -> StateToolResult:
        """Execute a tool call."""
        tool = self.tool_registry.get(tool_call.name)

        if not tool:
            return StateToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                result=f"Unknown tool: {tool_call.name}",
                success=False,
            )

        # Check if tool is allowed in current mode
        if not tool.is_allowed_in_mode(self.state.mode):
            return StateToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                result=f"Tool '{tool_call.name}' is not allowed in {self.state.mode.value} mode",
                success=False,
            )

        # Check if approval is needed
        if tool.requires_approval(self.state.mode):
            description = self._format_tool_description(tool_call)
            approved = self.approval_callback(tool_call.name, description, tool_call.arguments)

            if not approved:
                return StateToolResult(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    result="Tool execution was declined by user",
                    success=False,
                )

        # Execute the tool
        try:
            tool_result = await tool.execute(**tool_call.arguments)
            return StateToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                result=str(tool_result),
                success=tool_result.success,
            )
        except Exception as e:
            return StateToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                result=f"Tool execution error: {e}",
                success=False,
            )

    def _format_tool_description(self, tool_call: ToolCall) -> str:
        """Format a tool call for display to user."""
        args_str = json.dumps(tool_call.arguments, indent=2)
        return f"{tool_call.name}:\n{args_str}"

    def set_mode(self, mode: Mode) -> None:
        """Change the current mode."""
        self.state.set_mode(mode)

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.state.clear()

    def populate_tasks_from_plan(self) -> None:
        """Populate task list from current plan."""
        if self.current_plan:
            tasks = self.current_plan.to_tasks()
            if tasks:
                self.task_list.clear_all()
                self.task_list.add_tasks(tasks)

    async def close(self) -> None:
        """Clean up resources."""
        await self.provider.close()
