"""Pytest configuration and fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from lizcode.core.plan import Plan
from lizcode.core.state import ConversationState, Mode
from lizcode.core.tasks import TaskList
from lizcode.tools.bash import BashTool
from lizcode.tools.todo_write import TodoWriteTool


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def task_list(temp_dir: Path) -> TaskList:
    """Create a TaskList with persistence path."""
    tl = TaskList()
    tl.set_persist_path(temp_dir / "tasks.json")
    return tl


@pytest.fixture  
def todo_tool(task_list: TaskList) -> TodoWriteTool:
    """Create a TodoWriteTool with task list."""
    tool = TodoWriteTool(task_list=task_list)
    return tool


@pytest.fixture
def conversation_state() -> ConversationState:
    """Create a ConversationState."""
    return ConversationState()


@pytest.fixture
def plan(temp_dir: Path) -> Plan:
    """Create a Plan with persistence path."""
    p = Plan(title="Test Plan", objective="Test objective")
    p.set_persist_path(temp_dir / "plan")
    return p


@pytest.fixture
def bash_tool() -> BashTool:
    """Create a BashTool."""
    return BashTool(timeout=10)
