"""Tools for LizCode."""

from lizcode.tools.base import Permission, Tool, ToolRegistry, ToolResult
from lizcode.tools.bash import BashTool
from lizcode.tools.browser import BrowserTool
from lizcode.tools.completion import AttemptCompletionTool
from lizcode.tools.edit_file import EditFileTool
from lizcode.tools.glob import GlobTool
from lizcode.tools.grep import GrepTool
from lizcode.tools.list_files import ListFilesTool
from lizcode.tools.mode import CreatePlanTool, FinalizePlanTool, UpdatePlanTool
from lizcode.tools.notebook import NotebookEditTool
from lizcode.tools.read_file import ReadFileTool
from lizcode.tools.skill import SkillTool
from lizcode.tools.task import AskUserQuestionTool, TaskTool
from lizcode.tools.todo_write import TodoWriteTool
from lizcode.tools.webfetch import WebFetchTool
from lizcode.tools.write_file import WriteFileTool

__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "Permission",
    # File tools
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "GlobTool",
    "GrepTool",
    "ListFilesTool",
    # AI management tools
    "TodoWriteTool",
    "TaskTool",
    "AskUserQuestionTool",
    "AttemptCompletionTool",
    # Plan tools (Plan mode only)
    "CreatePlanTool",
    "FinalizePlanTool",
    "UpdatePlanTool",
    # Web tools
    "WebFetchTool",
    "BrowserTool",
    # Skills
    "SkillTool",
    # Notebook
    "NotebookEditTool",
]


def get_default_tools() -> list[Tool]:
    """Get the default set of tools."""
    return [
        # File operations
        BashTool(),
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        GlobTool(),
        GrepTool(),
        ListFilesTool(),
        # Task management
        TodoWriteTool(),
        TaskTool(),
        AskUserQuestionTool(),
        AttemptCompletionTool(),
        # Plan tools (Plan mode only)
        CreatePlanTool(),
        FinalizePlanTool(),
        UpdatePlanTool(),
        # Web
        WebFetchTool(),
        BrowserTool(),
        # Skills
        SkillTool(),
        # Notebook
        NotebookEditTool(),
    ]


def create_tool_registry() -> ToolRegistry:
    """Create a tool registry with default tools."""
    registry = ToolRegistry()
    for tool in get_default_tools():
        registry.register(tool)
    return registry
