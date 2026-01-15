"""Task/Todo management system for LizCode."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class TaskState(Enum):
    """State of a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

    def __str__(self) -> str:
        return self.value


@dataclass
class Task:
    """A single task in the todo list."""

    id: str
    content: str  # Imperative form: "Run tests"
    active_form: str  # Present continuous: "Running tests"
    state: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    parent_id: str | None = None  # For subtasks
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """Mark task as in progress."""
        self.state = TaskState.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self) -> None:
        """Mark task as completed."""
        self.state = TaskState.COMPLETED
        self.completed_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "active_form": self.active_form,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            active_form=data["active_form"],
            state=TaskState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            parent_id=data.get("parent_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskList:
    """Manages a list of tasks with state tracking."""

    tasks: list[Task] = field(default_factory=list)
    _persist_path: Path | None = None

    def add_task(
        self,
        content: str,
        active_form: str,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Add a new task."""
        task = Task(
            id=str(uuid4())[:8],
            content=content,
            active_form=active_form,
            parent_id=parent_id,
            metadata=metadata or {},
        )
        self.tasks.append(task)
        self._persist()
        return task

    def add_tasks(self, tasks: list[dict[str, str]]) -> list[Task]:
        """Add multiple tasks at once.
        
        Each dict should have 'content' and 'active_form' keys.
        """
        created = []
        for task_data in tasks:
            task = self.add_task(
                content=task_data["content"],
                active_form=task_data["active_form"],
                parent_id=task_data.get("parent_id"),
                metadata=task_data.get("metadata"),
            )
            created.append(task)
        return created

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def start_task(self, task_id: str) -> Task | None:
        """Mark a task as in progress.
        
        Enforces that only one task can be in_progress at a time.
        """
        # Check if another task is already in progress
        current = self.get_in_progress()
        if current and current.id != task_id:
            raise ValueError(
                f"Cannot start task {task_id}: task '{current.content}' is already in progress. "
                "Complete it first or mark it as pending."
            )

        task = self.get_task(task_id)
        if task:
            task.start()
            self._persist()
        return task

    def complete_task(self, task_id: str) -> Task | None:
        """Mark a task as completed."""
        task = self.get_task(task_id)
        if task:
            task.complete()
            self._persist()
        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the list."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(i)
                self._persist()
                return True
        return False

    def get_pending(self) -> list[Task]:
        """Get all pending tasks."""
        return [t for t in self.tasks if t.state == TaskState.PENDING]

    def get_in_progress(self) -> Task | None:
        """Get the currently in-progress task (should be at most one)."""
        for task in self.tasks:
            if task.state == TaskState.IN_PROGRESS:
                return task
        return None

    def get_completed(self) -> list[Task]:
        """Get all completed tasks."""
        return [t for t in self.tasks if t.state == TaskState.COMPLETED]

    def get_next_pending(self) -> Task | None:
        """Get the next pending task to work on."""
        pending = self.get_pending()
        return pending[0] if pending else None

    def clear_completed(self) -> int:
        """Remove all completed tasks. Returns count removed."""
        original_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.state != TaskState.COMPLETED]
        removed = original_count - len(self.tasks)
        if removed > 0:
            self._persist()
        return removed

    def clear_all(self) -> None:
        """Clear all tasks."""
        self.tasks.clear()
        self._persist()

    def to_display(self) -> str:
        """Format tasks for display with IDs (needed for start/complete actions).
        
        Format: [id] [state] content
        - [id] [ ] content   - pending
        - [id] [>] content   - in progress (shows active_form)
        - [id] [x] content   - completed
        """
        if not self.tasks:
            return "No tasks."

        lines = []
        for task in self.tasks:
            if task.state == TaskState.PENDING:
                lines.append(f"[{task.id}] [ ] {task.content}")
            elif task.state == TaskState.IN_PROGRESS:
                lines.append(f"[{task.id}] [>] {task.active_form}")
            else:
                lines.append(f"[{task.id}] [x] {task.content}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskList:
        """Create from dictionary."""
        task_list = cls()
        task_list.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        return task_list

    def set_persist_path(self, path: Path) -> None:
        """Set path for auto-persistence."""
        self._persist_path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def _persist(self) -> None:
        """Save to disk if persist path is set."""
        if self._persist_path:
            self._persist_path.write_text(
                json.dumps(self.to_dict(), indent=2, default=str)
            )

    @classmethod
    def load(cls, path: Path) -> TaskList:
        """Load task list from file."""
        if not path.exists():
            task_list = cls()
            task_list.set_persist_path(path)
            return task_list

        data = json.loads(path.read_text())
        task_list = cls.from_dict(data)
        task_list.set_persist_path(path)
        return task_list

    def get_progress(self) -> tuple[int, int]:
        """Get (completed_count, total_count)."""
        completed = len(self.get_completed())
        total = len(self.tasks)
        return completed, total

    def get_progress_display(self) -> str:
        """Get progress as a display string."""
        completed, total = self.get_progress()
        if total == 0:
            return "No tasks"
        percentage = int((completed / total) * 100)
        return f"{completed}/{total} ({percentage}%)"
