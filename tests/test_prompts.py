"""Tests for prompt generation and tool visibility."""

from __future__ import annotations

import pytest

from lizcode.core.prompts import get_system_prompt, get_tool_list_for_prompt
from lizcode.core.state import Mode
from lizcode.tools import create_tool_registry


class TestToolVisibility:
    """Test that tools are correctly visible/hidden based on mode and state."""

    @pytest.fixture
    def registry(self):
        return create_tool_registry()

    def test_plan_mode_no_plan_has_create_plan(self, registry) -> None:
        """Plan mode without a plan should have create_plan tool."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=False)
        tool_names = [t.name for t in tools]
        
        assert "create_plan" in tool_names, "create_plan should be available when no plan exists"

    def test_plan_mode_no_plan_no_update_finalize(self, registry) -> None:
        """Plan mode without a plan should NOT have update_plan or finalize_plan."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=False)
        tool_names = [t.name for t in tools]
        
        assert "update_plan" not in tool_names, "update_plan requires existing plan"
        assert "finalize_plan" not in tool_names, "finalize_plan requires existing plan"

    def test_plan_mode_with_plan_has_update_finalize(self, registry) -> None:
        """Plan mode with a plan should have update_plan and finalize_plan."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=True)
        tool_names = [t.name for t in tools]
        
        assert "update_plan" in tool_names, "update_plan should be available with plan"
        assert "finalize_plan" in tool_names, "finalize_plan should be available with plan"

    def test_plan_mode_with_plan_still_has_create_plan(self, registry) -> None:
        """Plan mode with a plan should still have create_plan for restart."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=True)
        tool_names = [t.name for t in tools]
        
        assert "create_plan" in tool_names, "create_plan should be available to restart plan"

    def test_plan_mode_has_read_tools(self, registry) -> None:
        """Plan mode should have read-only tools."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=False)
        tool_names = [t.name for t in tools]
        
        # Essential read tools that should always be in plan mode
        assert "read_file" in tool_names
        assert "list_files" in tool_names
        assert "glob" in tool_names
        assert "grep" in tool_names

    def test_plan_mode_no_write_tools(self, registry) -> None:
        """Plan mode should NOT have write/execute tools."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=False)
        tool_names = [t.name for t in tools]
        
        # These should NOT be in plan mode
        assert "bash" not in tool_names, "bash is ACT only"
        assert "write_file" not in tool_names, "write_file is ACT only"
        assert "edit_file" not in tool_names, "edit_file is ACT only"
        assert "attempt_completion" not in tool_names, "attempt_completion is ACT only"

    def test_plan_mode_has_todo_write_for_list(self, registry) -> None:
        """Plan mode should have todo_write (for list action only)."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=False)
        tool_names = [t.name for t in tools]
        
        assert "todo_write" in tool_names, "todo_write should be in Plan mode for list action"
        
        # Also check with plan
        tools_with_plan = registry.get_for_context(Mode.PLAN, has_plan=True)
        tool_names_with_plan = [t.name for t in tools_with_plan]
        
        assert "todo_write" in tool_names_with_plan, "todo_write should be in Plan mode for list action"

    def test_act_mode_has_write_tools(self, registry) -> None:
        """Act mode should have write tools."""
        tools = registry.get_for_context(Mode.ACT, has_plan=False)
        tool_names = [t.name for t in tools]
        
        assert "bash" in tool_names
        assert "write_file" in tool_names
        assert "edit_file" in tool_names
        assert "todo_write" in tool_names
        assert "attempt_completion" in tool_names

    def test_act_mode_no_plan_tools(self, registry) -> None:
        """Act mode should NOT have plan tools."""
        tools = registry.get_for_context(Mode.ACT, has_plan=False)
        tool_names = [t.name for t in tools]
        
        assert "create_plan" not in tool_names, "create_plan is PLAN mode only"
        assert "update_plan" not in tool_names, "update_plan is PLAN mode only"
        assert "finalize_plan" not in tool_names, "finalize_plan is PLAN mode only"

    def test_act_mode_still_has_read_tools(self, registry) -> None:
        """Act mode should still have read tools."""
        tools = registry.get_for_context(Mode.ACT, has_plan=False)
        tool_names = [t.name for t in tools]
        
        assert "read_file" in tool_names
        assert "list_files" in tool_names
        assert "glob" in tool_names
        assert "grep" in tool_names


class TestPromptToolList:
    """Test that the system prompt correctly reflects available tools."""

    @pytest.fixture
    def registry(self):
        return create_tool_registry()

    def test_prompt_plan_mode_shows_correct_tools(self, registry) -> None:
        """Plan mode prompt should list only plan-appropriate tools."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=False)
        prompt = get_system_prompt(
            mode=Mode.PLAN,
            working_directory="/test",
            available_tools=tools,
            has_plan=False,
        )
        
        # Should have read tools listed
        assert "read_file" in prompt
        assert "list_files" in prompt
        assert "create_plan" in prompt
        
        # Should NOT have write tools listed
        assert "bash:" not in prompt  # Use colon to avoid matching "bash mode"
        assert "write_file" not in prompt
        assert "edit_file" not in prompt
        assert "attempt_completion" not in prompt

    def test_prompt_act_mode_shows_correct_tools(self, registry) -> None:
        """Act mode prompt should list write tools, not plan tools."""
        tools = registry.get_for_context(Mode.ACT, has_plan=False)
        prompt = get_system_prompt(
            mode=Mode.ACT,
            working_directory="/test",
            available_tools=tools,
            has_plan=False,
        )
        
        # Should have write tools listed
        assert "bash" in prompt
        assert "write_file" in prompt
        assert "edit_file" in prompt
        assert "attempt_completion" in prompt
        
        # Should NOT have plan tools listed
        assert "create_plan" not in prompt
        assert "update_plan" not in prompt
        assert "finalize_plan" not in prompt

    def test_prompt_plan_with_plan_has_all_plan_tools(self, registry) -> None:
        """Plan mode with existing plan should show all plan tools including create_plan."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=True)
        prompt = get_system_prompt(
            mode=Mode.PLAN,
            working_directory="/test",
            available_tools=tools,
            has_plan=True,
        )
        
        # Should have plan management tools
        assert "update_plan" in prompt
        assert "finalize_plan" in prompt
        
        # Should ALSO have create_plan (for restarting plan)
        tool_list = get_tool_list_for_prompt(tools)
        assert "create_plan" in tool_list, "create_plan should be available to restart plan"

    def test_tool_list_matches_api_tools(self, registry) -> None:
        """The tools shown in prompt should match what's sent to API."""
        for mode in [Mode.PLAN, Mode.ACT]:
            for has_plan in [False, True]:
                tools = registry.get_for_context(mode, has_plan)
                tool_list_str = get_tool_list_for_prompt(tools)
                
                # Every tool in the list should appear in the string
                for tool in tools:
                    assert tool.name in tool_list_str, \
                        f"Tool {tool.name} missing from prompt for mode={mode}, has_plan={has_plan}"


class TestTodoWriteModeValidation:
    """Test that todo_write validates actions based on mode."""

    @pytest.mark.asyncio
    async def test_todo_write_list_allowed_in_plan_mode(self) -> None:
        """todo_write(list) should work in Plan mode."""
        from lizcode.core.tasks import TaskList
        from lizcode.tools.todo_write import TodoWriteTool
        
        task_list = TaskList()
        task_list.add_task("Test task", "Testing")
        
        tool = TodoWriteTool(task_list)
        tool.set_mode(Mode.PLAN)
        
        result = await tool.execute(action="list")
        
        assert result.success, f"list should work in Plan mode: {result.error}"
        assert "Test task" in result.output

    @pytest.mark.asyncio
    async def test_todo_write_create_blocked_in_plan_mode(self) -> None:
        """todo_write(create) should fail in Plan mode."""
        from lizcode.core.tasks import TaskList
        from lizcode.tools.todo_write import TodoWriteTool
        
        task_list = TaskList()
        tool = TodoWriteTool(task_list)
        tool.set_mode(Mode.PLAN)
        
        result = await tool.execute(
            action="create",
            tasks=[{"content": "Test", "active_form": "Testing"}],
        )
        
        assert not result.success, "create should fail in Plan mode"
        assert "not allowed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_todo_write_start_blocked_in_plan_mode(self) -> None:
        """todo_write(start) should fail in Plan mode."""
        from lizcode.core.tasks import TaskList
        from lizcode.tools.todo_write import TodoWriteTool
        
        task_list = TaskList()
        task = task_list.add_task("Test", "Testing")
        
        tool = TodoWriteTool(task_list)
        tool.set_mode(Mode.PLAN)
        
        result = await tool.execute(action="start", task_id=task.id)
        
        assert not result.success, "start should fail in Plan mode"
        assert "not allowed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_todo_write_all_actions_work_in_act_mode(self) -> None:
        """todo_write should allow all actions in Act mode."""
        from lizcode.core.tasks import TaskList
        from lizcode.tools.todo_write import TodoWriteTool
        
        task_list = TaskList()
        tool = TodoWriteTool(task_list)
        tool.set_mode(Mode.ACT)
        
        # Create
        result = await tool.execute(
            action="create",
            tasks=[{"content": "Test", "active_form": "Testing"}],
        )
        assert result.success, f"create should work in Act mode: {result.error}"
        
        # Get task ID
        task_id = task_list.tasks[0].id
        
        # Start
        result = await tool.execute(action="start", task_id=task_id)
        assert result.success, f"start should work in Act mode: {result.error}"
        
        # Complete
        result = await tool.execute(action="complete", task_id=task_id)
        assert result.success, f"complete should work in Act mode: {result.error}"


class TestNotebookModeValidation:
    """Test that notebook_edit validates actions based on mode."""

    @pytest.mark.asyncio
    async def test_notebook_read_allowed_in_plan_mode(self, tmp_path) -> None:
        """notebook_edit(read) should work in Plan mode."""
        from lizcode.tools.notebook import NotebookEditTool
        
        # Create a test notebook
        notebook_path = tmp_path / "test.ipynb"
        notebook_path.write_text('{"cells": [{"cell_type": "code", "source": ["print(1)"]}], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}')
        
        tool = NotebookEditTool()
        tool.set_mode(Mode.PLAN)
        
        result = await tool.execute(action="read", notebook_path=str(notebook_path))
        
        assert result.success, f"read should work in Plan mode: {result.error}"
        assert "print(1)" in result.output

    @pytest.mark.asyncio
    async def test_notebook_edit_blocked_in_plan_mode(self, tmp_path) -> None:
        """notebook_edit(edit) should fail in Plan mode."""
        from lizcode.tools.notebook import NotebookEditTool
        
        notebook_path = tmp_path / "test.ipynb"
        notebook_path.write_text('{"cells": [{"cell_type": "code", "source": ["print(1)"]}], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}')
        
        tool = NotebookEditTool()
        tool.set_mode(Mode.PLAN)
        
        result = await tool.execute(
            action="edit",
            notebook_path=str(notebook_path),
            cell_number=0,
            source="print(2)",
        )
        
        assert not result.success, "edit should fail in Plan mode"
        assert "not allowed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_notebook_all_actions_work_in_act_mode(self, tmp_path) -> None:
        """notebook_edit should allow all actions in Act mode."""
        from lizcode.tools.notebook import NotebookEditTool
        
        notebook_path = tmp_path / "test.ipynb"
        
        tool = NotebookEditTool()
        tool.set_mode(Mode.ACT)
        
        # Insert (creates notebook)
        result = await tool.execute(
            action="insert",
            notebook_path=str(notebook_path),
            cell_number=0,
            source="print(1)",
        )
        assert result.success, f"insert should work in Act mode: {result.error}"
        
        # Edit
        result = await tool.execute(
            action="edit",
            notebook_path=str(notebook_path),
            cell_number=0,
            source="print(2)",
        )
        assert result.success, f"edit should work in Act mode: {result.error}"
        
        # Read
        result = await tool.execute(action="read", notebook_path=str(notebook_path))
        assert result.success, f"read should work in Act mode: {result.error}"


class TestModeInstructions:
    """Test that mode-specific instructions are correct."""

    @pytest.fixture
    def registry(self):
        return create_tool_registry()

    def test_plan_mode_instructions_mention_create_plan(self, registry) -> None:
        """Plan mode without plan should mention create_plan."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=False)
        prompt = get_system_prompt(
            mode=Mode.PLAN,
            working_directory="/test", 
            available_tools=tools,
            has_plan=False,
        )
        
        assert "create_plan" in prompt

    def test_plan_mode_with_plan_instructions_different(self, registry) -> None:
        """Plan mode with plan should have different instructions."""
        tools = registry.get_for_context(Mode.PLAN, has_plan=True)
        prompt = get_system_prompt(
            mode=Mode.PLAN,
            working_directory="/test",
            available_tools=tools,
            has_plan=True,
        )
        
        assert "update_plan" in prompt
        assert "finalize_plan" in prompt

    def test_act_mode_instructions_mention_attempt_completion(self, registry) -> None:
        """Act mode should emphasize attempt_completion."""
        tools = registry.get_for_context(Mode.ACT, has_plan=False)
        prompt = get_system_prompt(
            mode=Mode.ACT,
            working_directory="/test",
            available_tools=tools,
            has_plan=False,
        )
        
        assert "attempt_completion" in prompt
