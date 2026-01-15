"""Tests for TaskList and task management."""

from __future__ import annotations

import pytest

from lizcode.core.tasks import Task, TaskList, TaskState


class TestTask:
    """Tests for individual Task objects."""

    def test_task_creation(self) -> None:
        """Test task creation with defaults."""
        task = Task(
            id="abc123",
            content="Fix bug",
            active_form="Fixing bug",
        )
        assert task.id == "abc123"
        assert task.content == "Fix bug"
        assert task.active_form == "Fixing bug"
        assert task.state == TaskState.PENDING
        assert task.started_at is None
        assert task.completed_at is None

    def test_task_start(self) -> None:
        """Test starting a task."""
        task = Task(id="1", content="Test", active_form="Testing")
        task.start()
        
        assert task.state == TaskState.IN_PROGRESS
        assert task.started_at is not None

    def test_task_complete(self) -> None:
        """Test completing a task."""
        task = Task(id="1", content="Test", active_form="Testing")
        task.start()
        task.complete()
        
        assert task.state == TaskState.COMPLETED
        assert task.completed_at is not None

    def test_task_serialization(self) -> None:
        """Test task to_dict and from_dict."""
        task = Task(
            id="abc",
            content="Test",
            active_form="Testing",
            metadata={"key": "value"},
        )
        task.start()
        
        data = task.to_dict()
        restored = Task.from_dict(data)
        
        assert restored.id == task.id
        assert restored.content == task.content
        assert restored.state == TaskState.IN_PROGRESS
        assert restored.metadata == {"key": "value"}


class TestTaskList:
    """Tests for TaskList management."""

    def test_add_task(self, task_list: TaskList) -> None:
        """Test adding a single task."""
        task = task_list.add_task(
            content="Fix bug",
            active_form="Fixing bug",
        )
        
        assert task.id is not None
        assert len(task.id) == 8
        assert task.content == "Fix bug"
        assert len(task_list.tasks) == 1

    def test_add_multiple_tasks(self, task_list: TaskList) -> None:
        """Test adding multiple tasks at once."""
        tasks_data = [
            {"content": "Task 1", "active_form": "Doing task 1"},
            {"content": "Task 2", "active_form": "Doing task 2"},
            {"content": "Task 3", "active_form": "Doing task 3"},
        ]
        
        created = task_list.add_tasks(tasks_data)
        
        assert len(created) == 3
        assert len(task_list.tasks) == 3
        assert all(t.state == TaskState.PENDING for t in created)

    def test_get_task(self, task_list: TaskList) -> None:
        """Test getting a task by ID."""
        task = task_list.add_task("Test", "Testing")
        
        found = task_list.get_task(task.id)
        assert found is task
        
        not_found = task_list.get_task("nonexistent")
        assert not_found is None

    def test_start_task(self, task_list: TaskList) -> None:
        """Test starting a task."""
        task = task_list.add_task("Test", "Testing")
        
        started = task_list.start_task(task.id)
        
        assert started is task
        assert started.state == TaskState.IN_PROGRESS

    def test_only_one_task_in_progress(self, task_list: TaskList) -> None:
        """Test that only one task can be in progress at a time."""
        task1 = task_list.add_task("Task 1", "Doing 1")
        task2 = task_list.add_task("Task 2", "Doing 2")
        
        task_list.start_task(task1.id)
        
        with pytest.raises(ValueError, match="already in progress"):
            task_list.start_task(task2.id)

    def test_complete_task(self, task_list: TaskList) -> None:
        """Test completing a task."""
        task = task_list.add_task("Test", "Testing")
        task_list.start_task(task.id)
        
        completed = task_list.complete_task(task.id)
        
        assert completed is task
        assert completed.state == TaskState.COMPLETED

    def test_remove_task(self, task_list: TaskList) -> None:
        """Test removing a task."""
        task = task_list.add_task("Test", "Testing")
        
        removed = task_list.remove_task(task.id)
        
        assert removed is True
        assert len(task_list.tasks) == 0

    def test_get_pending(self, task_list: TaskList) -> None:
        """Test getting pending tasks."""
        task1 = task_list.add_task("Task 1", "Doing 1")
        task2 = task_list.add_task("Task 2", "Doing 2")
        task_list.start_task(task1.id)
        
        pending = task_list.get_pending()
        
        assert len(pending) == 1
        assert pending[0] is task2

    def test_get_in_progress(self, task_list: TaskList) -> None:
        """Test getting in-progress task."""
        task = task_list.add_task("Task", "Doing task")
        
        assert task_list.get_in_progress() is None
        
        task_list.start_task(task.id)
        
        assert task_list.get_in_progress() is task

    def test_clear_completed(self, task_list: TaskList) -> None:
        """Test clearing completed tasks."""
        task1 = task_list.add_task("Task 1", "Doing 1")
        task2 = task_list.add_task("Task 2", "Doing 2")
        
        task_list.start_task(task1.id)
        task_list.complete_task(task1.id)
        
        removed = task_list.clear_completed()
        
        assert removed == 1
        assert len(task_list.tasks) == 1
        assert task_list.tasks[0] is task2

    def test_to_display(self, task_list: TaskList) -> None:
        """Test task list display format."""
        task1 = task_list.add_task("Task 1", "Doing task 1")
        task2 = task_list.add_task("Task 2", "Doing task 2")
        task3 = task_list.add_task("Task 3", "Doing task 3")
        
        task_list.start_task(task1.id)
        task_list.complete_task(task1.id)
        task_list.start_task(task2.id)
        
        display = task_list.to_display()
        
        # Format should be [id] [state] content
        assert f"[{task1.id}] [x]" in display
        assert f"[{task2.id}] [>]" in display
        assert f"[{task3.id}] [ ]" in display
        
        # In-progress should show active form
        assert "Doing task 2" in display
        
        # Completed should show content
        assert "Task 1" in display

    def test_progress_display(self, task_list: TaskList) -> None:
        """Test progress display string."""
        task1 = task_list.add_task("Task 1", "Doing 1")
        task2 = task_list.add_task("Task 2", "Doing 2")
        
        assert "0/2" in task_list.get_progress_display()
        
        task_list.start_task(task1.id)
        task_list.complete_task(task1.id)
        
        assert "1/2" in task_list.get_progress_display()

    def test_persistence(self, task_list: TaskList, temp_dir) -> None:
        """Test that tasks are persisted to disk."""
        task = task_list.add_task("Test", "Testing")
        
        # Load a new TaskList from same path
        loaded = TaskList.load(temp_dir / "tasks.json")
        
        assert len(loaded.tasks) == 1
        assert loaded.tasks[0].content == "Test"


class TestTaskListFromPlan:
    """Test task list integration with plan."""

    def test_tasks_from_plan_steps(self, plan) -> None:
        """Test converting plan steps to tasks."""
        from lizcode.core.plan import PlanStep
        
        plan.add_step(PlanStep(
            description="Fix the bug",
            files_involved=["main.py"],
        ))
        plan.add_step(PlanStep(
            description="Add tests",
        ))
        
        tasks = plan.to_tasks()
        
        assert len(tasks) == 2
        assert tasks[0]["content"] == "Fix the bug"
        assert "Fixing" in tasks[0]["active_form"]
        assert tasks[1]["content"] == "Add tests"
        assert "Adding" in tasks[1]["active_form"]

    def test_verification_not_included_as_tasks(self, plan) -> None:
        """Test that verification steps are NOT included as tasks."""
        from lizcode.core.plan import PlanStep
        
        plan.add_step(PlanStep(description="Do the work"))
        plan.add_verification("Run tests to verify")
        plan.add_verification("Check manually")
        
        tasks = plan.to_tasks()
        
        # Only implementation step, not verification
        assert len(tasks) == 1
        assert tasks[0]["content"] == "Do the work"
