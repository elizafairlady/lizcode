"""Integration tests for agent workflows using mock provider."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from lizcode.core.agent import Agent
from lizcode.core.state import ConversationState, Mode
from lizcode.core.tasks import TaskList
from tests.mock_provider import MockProvider


class TestActModeWorkflow:
    """Test act mode task workflow."""

    @pytest.mark.asyncio
    async def test_works_through_5_tasks(self, temp_dir: Path) -> None:
        """Test that agent works through 5 tasks in order."""
        # Set up task list  
        task_list = TaskList()
        task_list.set_persist_path(temp_dir / "tasks.json")
        
        # Create 5 tasks
        tasks_data = [
            {"content": f"Task {i}", "active_form": f"Doing task {i}"}
            for i in range(5)
        ]
        created = task_list.add_tasks(tasks_data)
        task_ids = [t.id for t in created]
        
        # Create mock provider that works through tasks properly
        provider = MockProvider()
        
        for i, task_id in enumerate(task_ids):
            # Start task
            provider.add_response(
                content=f"Starting task {i}.",
                tool_calls=[{
                    "name": "todo_write",
                    "arguments": {"action": "start", "task_id": task_id},
                }],
            )
            # Complete task
            provider.add_response(
                content=f"Task {i} done.",
                tool_calls=[{
                    "name": "todo_write",
                    "arguments": {"action": "complete", "task_id": task_id},
                }],
            )
        
        # Final completion
        provider.add_response(
            content="All done!",
            tool_calls=[{
                "name": "attempt_completion",
                "arguments": {"result": "Completed 5 tasks"},
            }],
        )
        
        # Create agent
        state = ConversationState()
        state.set_mode(Mode.ACT)
        
        agent = Agent(
            provider=provider,
            state=state,
            working_directory=temp_dir,
        )
        # Override task list with our pre-populated one
        agent.task_list = task_list
        # Also wire the todo_write tool to use our task list
        from lizcode.tools.todo_write import TodoWriteTool
        for tool in agent.tool_registry.get_all():
            if isinstance(tool, TodoWriteTool):
                tool.set_task_list(task_list)
        
        # Run agent
        chunks = []
        async for chunk in agent.chat("Go"):
            chunks.append(chunk)
        
        # Check all tasks completed
        assert len(task_list.get_completed()) == 5
        assert len(task_list.get_pending()) == 0
        
        # Check attempt_completion was called (filter for tool_call type only)
        completion_calls = [
            c for c in chunks 
            if c.get("tool") == "attempt_completion" and c.get("type") == "tool_call"
        ]
        assert len(completion_calls) == 1

    @pytest.mark.asyncio
    async def test_works_through_10_tasks(self, temp_dir: Path) -> None:
        """Test that agent handles 10 tasks without getting lost.
        
        Note: ACT mode has iteration limit of 25, so 10 tasks (20 tool calls) fits.
        """
        task_list = TaskList()
        task_list.set_persist_path(temp_dir / "tasks.json")
        
        # Create 10 tasks (20 iterations for start/complete + 1 for attempt_completion = 21)
        tasks_data = [
            {"content": f"Task {i}", "active_form": f"Doing task {i}"}
            for i in range(10)
        ]
        created = task_list.add_tasks(tasks_data)
        task_ids = [t.id for t in created]
        
        # Mock provider for 10 tasks
        provider = MockProvider()
        for i, task_id in enumerate(task_ids):
            provider.add_response(
                tool_calls=[{"name": "todo_write", "arguments": {"action": "start", "task_id": task_id}}],
            )
            provider.add_response(
                tool_calls=[{"name": "todo_write", "arguments": {"action": "complete", "task_id": task_id}}],
            )
        provider.add_response(
            tool_calls=[{"name": "attempt_completion", "arguments": {"result": "Done"}}],
        )
        
        state = ConversationState()
        state.set_mode(Mode.ACT)
        
        agent = Agent(provider=provider, state=state, working_directory=temp_dir)
        agent.task_list = task_list
        # Wire the tool
        from lizcode.tools.todo_write import TodoWriteTool
        for tool in agent.tool_registry.get_all():
            if isinstance(tool, TodoWriteTool):
                tool.set_task_list(task_list)
        
        async for _ in agent.chat("Go"):
            pass
        
        # All 10 should be complete
        assert len(task_list.get_completed()) == 10
        assert task_list.get_progress_display() == "10/10 (100%)"

    @pytest.mark.asyncio
    async def test_handles_iteration_limit(self, temp_dir: Path) -> None:
        """Test that iteration limit warning is emitted at 20 iterations."""
        provider = MockProvider()
        
        # Create 25 responses (will hit the iteration_warning_at=20)
        for i in range(30):
            provider.add_response(
                content=f"Response {i}",
                tool_calls=[{
                    "name": "read_file",
                    "arguments": {"file_path": f"file_{i}.txt"},
                }],
            )
        
        state = ConversationState()
        state.set_mode(Mode.ACT)
        
        agent = Agent(provider=provider, state=state, working_directory=temp_dir)
        
        iteration_limit_emitted = False
        async for chunk in agent.chat("Do stuff"):
            if chunk.get("type") == "iteration_limit":
                iteration_limit_emitted = True
                break  # Stop at iteration limit
        
        assert iteration_limit_emitted, "Should emit iteration_limit warning at 20"


class TestPlanModeWorkflow:
    """Test plan mode workflow."""

    @pytest.mark.asyncio
    async def test_creates_and_finalizes_plan(self, temp_dir: Path) -> None:
        """Test that planning workflow creates and finalizes a plan."""
        provider = MockProvider()
        
        # Create plan
        provider.add_response(
            content="I'll create a plan.",
            tool_calls=[{
                "name": "create_plan",
                "arguments": {
                    "title": "Test Plan",
                    "objective": "Test objective",
                },
            }],
        )
        
        # Add step
        provider.add_response(
            tool_calls=[{
                "name": "update_plan",
                "arguments": {
                    "action": "add_step",
                    "content": "Step 1",
                },
            }],
        )
        
        # Add another step
        provider.add_response(
            tool_calls=[{
                "name": "update_plan",
                "arguments": {
                    "action": "add_step",
                    "content": "Step 2",
                },
            }],
        )
        
        # Finalize
        provider.add_response(
            content="Plan ready!",
            tool_calls=[{
                "name": "finalize_plan",
                "arguments": {
                    "summary": "2-step plan",
                    "ready_to_implement": True,
                },
            }],
        )
        
        state = ConversationState()
        state.set_mode(Mode.PLAN)
        
        agent = Agent(provider=provider, state=state, working_directory=temp_dir)
        
        async for chunk in agent.chat("Create a plan"):
            pass
        
        # Check plan was created and finalized
        assert agent.current_plan is not None
        assert agent.current_plan.title == "Test Plan"
        assert len(agent.current_plan.steps) == 2
        from lizcode.core.plan import PlanPhase
        assert agent.current_plan.phase == PlanPhase.READY_TO_EXECUTE

    @pytest.mark.asyncio
    async def test_plan_converts_to_tasks(self, temp_dir: Path) -> None:
        """Test that finalized plan can be converted to tasks."""
        provider = MockProvider()
        
        provider.add_response(
            tool_calls=[{
                "name": "create_plan",
                "arguments": {"title": "Test", "objective": "Test"},
            }],
        )
        provider.add_response(
            tool_calls=[{
                "name": "update_plan",
                "arguments": {"action": "add_step", "content": "Do thing 1"},
            }],
        )
        provider.add_response(
            tool_calls=[{
                "name": "update_plan",
                "arguments": {"action": "add_step", "content": "Do thing 2"},
            }],
        )
        provider.add_response(
            tool_calls=[{
                "name": "update_plan",
                "arguments": {"action": "add_step", "content": "Do thing 3"},
            }],
        )
        provider.add_response(
            tool_calls=[{
                "name": "finalize_plan",
                "arguments": {"summary": "Done", "ready_to_implement": True},
            }],
        )
        
        state = ConversationState()
        state.set_mode(Mode.PLAN)
        
        agent = Agent(provider=provider, state=state, working_directory=temp_dir)
        
        async for _ in agent.chat("Plan"):
            pass
        
        # Convert to tasks
        agent.populate_tasks_from_plan()
        
        assert len(agent.task_list.tasks) == 3
        assert agent.task_list.tasks[0].content == "Do thing 1"


class TestBadBehaviorDetection:
    """Tests that help detect bad model behavior patterns."""

    @pytest.mark.asyncio
    async def test_detects_model_forgetting_tasks(self, temp_dir: Path) -> None:
        """Test scenario where model doesn't work through task list.
        
        This test documents what BAD behavior looks like - the model
        just does random edits without following the task list.
        """
        task_list = TaskList()
        task_list.set_persist_path(temp_dir / "tasks.json")
        
        # Create tasks
        for i in range(5):
            task_list.add_task(f"Task {i}", f"Doing {i}")
        
        # Bad provider - just does random stuff
        provider = MockProvider()
        for i in range(5):
            provider.add_response(
                content="Making changes",
                tool_calls=[{
                    "name": "read_file",
                    "arguments": {"file_path": f"random_{i}.txt"},
                }],
            )
        provider.add_response(content="I think I'm done!")  # No attempt_completion
        
        state = ConversationState()
        state.set_mode(Mode.ACT)
        
        agent = Agent(provider=provider, state=state, working_directory=temp_dir)
        agent.task_list = task_list
        
        async for _ in agent.chat("Go"):
            pass
        
        # BAD: No tasks completed, no attempt_completion
        assert len(task_list.get_completed()) == 0, "Bad model didn't complete any tasks"
        assert len(task_list.get_pending()) == 5, "All tasks still pending"

    @pytest.mark.asyncio
    async def test_detects_infinite_edit_loop(self, temp_dir: Path) -> None:
        """Test that iteration limit catches model stuck editing."""
        provider = MockProvider()
        
        # Model just keeps editing the same file
        for i in range(30):
            provider.add_response(
                content="Let me fix that...",
                tool_calls=[{
                    "name": "read_file",
                    "arguments": {"file_path": "main.py"},
                }],
            )
        
        state = ConversationState()
        state.set_mode(Mode.ACT)
        
        agent = Agent(provider=provider, state=state, working_directory=temp_dir)
        
        iterations = 0
        limit_hit = False
        async for chunk in agent.chat("Fix the bug"):
            if chunk.get("type") == "tool_call":
                iterations += 1
            if chunk.get("type") == "iteration_limit":
                limit_hit = True
                break
        
        # Should hit limit before 30 iterations
        assert limit_hit, "Iteration limit should prevent infinite loops"
        assert iterations < 25, f"Should stop before 25 tool calls, got {iterations}"
