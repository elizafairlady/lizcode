"""Scale tests for task management - 200+ tasks."""

from __future__ import annotations

import time

import pytest

from lizcode.core.tasks import TaskList, TaskState


class TestTaskListScale:
    """Test task list at scale."""

    def test_200_tasks_creation(self, task_list: TaskList) -> None:
        """Test creating 200 tasks."""
        tasks_data = [
            {"content": f"Task {i}", "active_form": f"Doing task {i}"}
            for i in range(200)
        ]
        
        start = time.time()
        created = task_list.add_tasks(tasks_data)
        elapsed = time.time() - start
        
        assert len(created) == 200
        assert len(task_list.tasks) == 200
        assert elapsed < 2.0, f"Creating 200 tasks took {elapsed}s - too slow"

    def test_200_tasks_display(self, task_list: TaskList) -> None:
        """Test display format with 200 tasks."""
        for i in range(200):
            task_list.add_task(f"Task {i}", f"Doing task {i}")
        
        start = time.time()
        display = task_list.to_display()
        elapsed = time.time() - start
        
        # Check format integrity
        lines = display.strip().split("\n")
        assert len(lines) == 200
        
        # Check all have proper format
        for line in lines:
            assert "] [ ]" in line or "] [>]" in line or "] [x]" in line
        
        assert elapsed < 1.0, f"Display took {elapsed}s - too slow"

    def test_200_tasks_sequential_completion(self, task_list: TaskList) -> None:
        """Test working through all 200 tasks in sequence."""
        for i in range(200):
            task_list.add_task(f"Task {i}", f"Doing task {i}")
        
        # Work through all tasks
        start = time.time()
        for task in list(task_list.tasks):
            task_list.start_task(task.id)
            task_list.complete_task(task.id)
        elapsed = time.time() - start
        
        # All should be completed
        assert len(task_list.get_completed()) == 200
        assert len(task_list.get_pending()) == 0
        assert task_list.get_in_progress() is None
        
        # Progress should show 200/200
        progress = task_list.get_progress_display()
        assert "200/200" in progress
        assert "100%" in progress
        
        assert elapsed < 5.0, f"200 tasks took {elapsed}s - too slow"

    def test_200_tasks_persistence(self, task_list: TaskList, temp_dir) -> None:
        """Test persisting and loading 200 tasks."""
        for i in range(200):
            task = task_list.add_task(f"Task {i}", f"Doing task {i}")
            if i < 50:
                task_list.start_task(task.id)
                task_list.complete_task(task.id)
            elif i < 51:
                task_list.start_task(task.id)
        
        # Load from disk
        loaded = TaskList.load(temp_dir / "tasks.json")
        
        assert len(loaded.tasks) == 200
        assert len(loaded.get_completed()) == 50
        assert loaded.get_in_progress() is not None
        assert len(loaded.get_pending()) == 149

    def test_200_tasks_context_size(self, task_list: TaskList) -> None:
        """Test that 200 tasks don't create an unreasonably large context."""
        for i in range(200):
            task_list.add_task(
                f"Implement feature {i}: This is a reasonable task description",
                f"Implementing feature {i}",
            )
        
        display = task_list.to_display()
        
        # Should be manageable - rough estimate ~100 chars per task
        # 200 * 100 = 20,000 chars = ~5,000 tokens
        assert len(display) < 30000, f"Display is {len(display)} chars - too large for context"

    def test_task_lookup_performance(self, task_list: TaskList) -> None:
        """Test that looking up tasks by ID is fast."""
        task_ids = []
        for i in range(200):
            task = task_list.add_task(f"Task {i}", f"Doing task {i}")
            task_ids.append(task.id)
        
        # Look up all tasks
        start = time.time()
        for task_id in task_ids:
            found = task_list.get_task(task_id)
            assert found is not None
        elapsed = time.time() - start
        
        # Should be O(n) but still fast
        assert elapsed < 1.0, f"200 lookups took {elapsed}s"

    def test_progress_at_various_stages(self, task_list: TaskList) -> None:
        """Test progress display at various completion stages."""
        for i in range(200):
            task_list.add_task(f"Task {i}", f"Doing task {i}")
        
        # Check at 0%
        progress = task_list.get_progress_display()
        assert "0/200" in progress
        assert "0%" in progress
        
        # Complete 50
        for task in task_list.tasks[:50]:
            task_list.start_task(task.id)
            task_list.complete_task(task.id)
        
        progress = task_list.get_progress_display()
        assert "50/200" in progress
        assert "25%" in progress
        
        # Complete remaining
        for task in task_list.tasks[50:]:
            task_list.start_task(task.id)
            task_list.complete_task(task.id)
        
        progress = task_list.get_progress_display()
        assert "200/200" in progress
        assert "100%" in progress
