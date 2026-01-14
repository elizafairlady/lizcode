"""Base tool class and registry for LizCode."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lizcode.core.state import Mode


class Permission(Enum):
    """Tool permission levels."""

    READ = "read"  # Read-only operations (auto-approved, both modes)
    WRITE = "write"  # File modifications (act mode only, requires approval)
    EXECUTE = "execute"  # Command execution (act mode only, requires approval)
    PLAN = "plan"  # Planning operations (plan mode only)


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: str
    error: str | None = None

    def __str__(self) -> str:
        if self.success:
            return self.output
        return f"Error: {self.error or self.output}"


class Tool(ABC):
    """Base class for all tools."""

    # Tool metadata - override in subclasses
    name: str = "base_tool"
    description: str = "Base tool description"
    permission: Permission = Permission.READ

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments."""
        ...

    def requires_approval(self, mode: Mode) -> bool:
        """Check if this tool requires user approval in the given mode."""
        if mode == Mode.PLAN:
            # In plan mode, READ and PLAN operations don't need approval
            # WRITE and EXECUTE are blocked entirely (see is_allowed_in_mode)
            return self.permission not in (Permission.READ, Permission.PLAN)

        if mode == Mode.ACT:
            # In act mode, WRITE and EXECUTE require approval
            # READ is auto-approved
            return self.permission in (Permission.WRITE, Permission.EXECUTE)

        # Bash mode - user is in control, no AI tool execution
        return True

    def is_allowed_in_mode(self, mode: Mode) -> bool:
        """Check if this tool can be used in the given mode."""
        if mode == Mode.PLAN:
            # READ and PLAN tools allowed in plan mode
            # WRITE and EXECUTE are blocked
            return self.permission in (Permission.READ, Permission.PLAN)

        if mode == Mode.ACT:
            # READ, WRITE, EXECUTE tools allowed in act mode
            # PLAN tools are NOT allowed - must be in Plan mode to plan
            return self.permission in (Permission.READ, Permission.WRITE, Permission.EXECUTE)

        # Bash mode - no AI tools
        return False

    def get_schema(self) -> dict[str, Any]:
        """Get the full tool schema for API calls."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolRegistry:
    """Registry for managing available tools."""

    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_for_mode(self, mode: Mode) -> list[Tool]:
        """Get tools available for a specific mode."""
        return [tool for tool in self._tools.values() if tool.is_allowed_in_mode(mode)]

    def get_for_context(self, mode: Mode, has_plan: bool = False) -> list[Tool]:
        """Get tools available for a specific mode AND state context.
        
        Args:
            mode: Current mode (PLAN, ACT, BASH)
            has_plan: Whether a plan has been created in this session
            
        Returns:
            List of tools appropriate for the current context
        """
        tools = []
        for tool in self._tools.values():
            # First check mode permission
            if not tool.is_allowed_in_mode(mode):
                continue
            
            # State-based filtering for plan tools in plan mode
            if mode == Mode.PLAN:
                if tool.name == "create_plan":
                    # Only offer create_plan if no plan exists
                    if has_plan:
                        continue
                elif tool.name in ("update_plan", "finalize_plan", "todo_write"):
                    # Only offer these if a plan exists
                    if not has_plan:
                        continue
            
            tools.append(tool)
        return tools

    def get_schemas(self, mode: Mode | None = None) -> list[dict[str, Any]]:
        """Get tool schemas, optionally filtered by mode."""
        tools = self.get_for_mode(mode) if mode else self.get_all()
        return [tool.get_schema() for tool in tools]

    def get_schemas_for_context(self, mode: Mode, has_plan: bool = False) -> list[dict[str, Any]]:
        """Get tool schemas filtered by mode AND state context."""
        tools = self.get_for_context(mode, has_plan)
        return [tool.get_schema() for tool in tools]
