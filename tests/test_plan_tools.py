"""Tests for plan tools: create_plan, update_plan, finalize_plan."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from lizcode.core.plan import Plan, PlanStep, PlanPhase


class MockAgent:
    """Mock agent for plan tool tests."""
    
    def __init__(self, working_directory: Path):
        self.current_plan = None
        self.task_list = MagicMock()
        self.task_list.clear_all = MagicMock()
        self.task_list.add_tasks = MagicMock()
        self.working_directory = working_directory


class TestCreatePlanTool:
    """Tests for create_plan tool."""

    @pytest.mark.asyncio
    async def test_creates_plan(self, tmp_path) -> None:
        """Should create a new plan."""
        from lizcode.tools.mode import CreatePlanTool
        
        tool = CreatePlanTool()
        agent = MockAgent(tmp_path)
        tool.set_state(agent)
        tool._working_dir = tmp_path
        
        result = await tool.execute(
            title="Test Plan",
            objective="Testing the plan system",
        )
        
        assert result.success
        assert agent.current_plan is not None
        assert agent.current_plan.title == "Test Plan"
        assert agent.current_plan.objective == "Testing the plan system"

    @pytest.mark.asyncio
    async def test_replaces_existing_plan(self, tmp_path) -> None:
        """Should replace existing plan when creating new one."""
        from lizcode.tools.mode import CreatePlanTool
        
        tool = CreatePlanTool()
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(
            title="Old Plan",
            objective="Old objective",
        )
        tool.set_state(agent)
        tool._working_dir = tmp_path
        
        result = await tool.execute(
            title="New Plan",
            objective="New objective",
        )
        
        assert result.success
        assert agent.current_plan.title == "New Plan"
        assert agent.current_plan.objective == "New objective"

    @pytest.mark.asyncio
    async def test_clears_tasks_on_new_plan(self, tmp_path) -> None:
        """Should clear existing tasks when creating new plan."""
        from lizcode.tools.mode import CreatePlanTool
        
        tool = CreatePlanTool()
        agent = MockAgent(tmp_path)
        tool.set_state(agent)
        tool._working_dir = tmp_path
        
        result = await tool.execute(
            title="Test",
            objective="Test",
        )
        
        assert result.success
        agent.task_list.clear_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_plan_file(self, tmp_path) -> None:
        """Should persist plan to disk."""
        from lizcode.tools.mode import CreatePlanTool
        
        tool = CreatePlanTool()
        agent = MockAgent(tmp_path)
        tool.set_state(agent)
        tool._working_dir = tmp_path
        
        result = await tool.execute(
            title="Persisted Plan",
            objective="Test persistence",
        )
        
        assert result.success
        
        plan_md = tmp_path / ".lizcode" / "plan.md"
        plan_json = tmp_path / ".lizcode" / "plan.json"
        assert plan_md.exists()
        assert plan_json.exists()


class TestUpdatePlanTool:
    """Tests for update_plan tool."""

    @pytest.mark.asyncio
    async def test_add_context(self, tmp_path) -> None:
        """Should add context to plan."""
        from lizcode.tools.mode import UpdatePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        
        tool = UpdatePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(action="add_context", content="Found the file structure")
        
        assert result.success
        assert "Found the file structure" in agent.current_plan.context_gathered

    @pytest.mark.asyncio
    async def test_add_step(self, tmp_path) -> None:
        """Should add implementation step."""
        from lizcode.tools.mode import UpdatePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        
        tool = UpdatePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(
            action="add_step",
            content="Implement the feature",
            files=["src/main.py"],
        )
        
        assert result.success
        assert len(agent.current_plan.steps) == 1
        assert agent.current_plan.steps[0].description == "Implement the feature"
        assert "src/main.py" in agent.current_plan.steps[0].files_involved

    @pytest.mark.asyncio
    async def test_add_file(self, tmp_path) -> None:
        """Should add critical file."""
        from lizcode.tools.mode import UpdatePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        
        tool = UpdatePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(action="add_file", content="config.py")
        
        assert result.success
        assert "config.py" in agent.current_plan.critical_files

    @pytest.mark.asyncio
    async def test_add_verification(self, tmp_path) -> None:
        """Should add verification step."""
        from lizcode.tools.mode import UpdatePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        
        tool = UpdatePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(action="add_verification", content="Run pytest")
        
        assert result.success
        assert "Run pytest" in agent.current_plan.verification_steps

    @pytest.mark.asyncio
    async def test_set_approach(self, tmp_path) -> None:
        """Should set approach with rationale."""
        from lizcode.tools.mode import UpdatePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        
        tool = UpdatePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(
            action="set_approach",
            content="Use dependency injection",
            rationale="Better testability",
        )
        
        assert result.success
        assert agent.current_plan.approach == "Use dependency injection"
        assert agent.current_plan.chosen_approach_rationale == "Better testability"

    @pytest.mark.asyncio
    async def test_add_risk(self, tmp_path) -> None:
        """Should add potential risk."""
        from lizcode.tools.mode import UpdatePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        
        tool = UpdatePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(action="add_risk", content="May break backwards compat")
        
        assert result.success
        assert "May break backwards compat" in agent.current_plan.potential_risks

    @pytest.mark.asyncio
    async def test_no_plan_error(self, tmp_path) -> None:
        """Should fail if no plan exists."""
        from lizcode.tools.mode import UpdatePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = None
        
        tool = UpdatePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(action="add_context", content="Something")
        
        assert not result.success
        assert "no" in result.error.lower() and "plan" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unknown_action(self, tmp_path) -> None:
        """Should fail on unknown action."""
        from lizcode.tools.mode import UpdatePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        
        tool = UpdatePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(action="invalid_action", content="Something")
        
        assert not result.success
        assert "unknown" in result.error.lower()


class TestFinalizePlanTool:
    """Tests for finalize_plan tool."""

    @pytest.mark.asyncio
    async def test_finalizes_plan(self, tmp_path) -> None:
        """Should mark plan as ready to execute."""
        from lizcode.tools.mode import FinalizePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        agent.current_plan.set_persist_path(tmp_path / ".lizcode" / "plan")
        
        tool = FinalizePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(summary="Ready to implement the feature")
        
        assert result.success
        assert agent.current_plan.phase == PlanPhase.READY_TO_EXECUTE
        assert "Ready to implement" in result.output

    @pytest.mark.asyncio
    async def test_finalize_not_ready(self, tmp_path) -> None:
        """Should set review phase if not ready."""
        from lizcode.tools.mode import FinalizePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        agent.current_plan.set_persist_path(tmp_path / ".lizcode" / "plan")
        
        tool = FinalizePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(summary="Need more info", ready_to_implement=False)
        
        assert result.success
        assert agent.current_plan.phase == PlanPhase.REVIEW

    @pytest.mark.asyncio
    async def test_summary_in_output(self, tmp_path) -> None:
        """Should include summary in output."""
        from lizcode.tools.mode import FinalizePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = Plan(title="Test", objective="Test")
        agent.current_plan.set_persist_path(tmp_path / ".lizcode" / "plan")
        agent.current_plan.add_step(PlanStep(description="Step 1"))
        
        tool = FinalizePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(summary="This plan adds feature X")
        
        assert result.success
        assert "This plan adds feature X" in result.output
        assert "Step 1" in result.output

    @pytest.mark.asyncio
    async def test_no_plan_success(self, tmp_path) -> None:
        """Should still succeed without a plan (edge case)."""
        from lizcode.tools.mode import FinalizePlanTool
        
        agent = MockAgent(tmp_path)
        agent.current_plan = None
        
        tool = FinalizePlanTool()
        tool.set_state(agent)
        
        result = await tool.execute(summary="No plan summary")
        
        # According to the implementation, this succeeds (just shows summary)
        assert result.success
        assert "No plan summary" in result.output
