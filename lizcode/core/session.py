"""Session management for LizCode - UUID-based session storage."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    """A single checkpoint within a session."""

    number: int
    message: str
    timestamp: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "message": self.message,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            number=data["number"],
            message=data["message"],
            timestamp=data["timestamp"],
        )


@dataclass
class Session:
    """A LizCode session with its own conversation, tasks, and checkpoints."""

    id: str
    name: str
    project_path: str
    created_at: str
    updated_at: str
    checkpoints: list[Checkpoint] = field(default_factory=list)
    
    _session_dir: Path | None = field(default=None, repr=False)

    @classmethod
    def create(cls, project_path: Path, name: str = "New Session") -> Session:
        """Create a new session with a fresh UUID."""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        session = cls(
            id=session_id,
            name=name,
            project_path=str(project_path.resolve()),
            created_at=now,
            updated_at=now,
        )
        return session

    @property
    def session_dir(self) -> Path | None:
        return self._session_dir

    def set_session_dir(self, path: Path) -> None:
        """Set the session directory path."""
        self._session_dir = path
        path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "project_path": self.project_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        return cls(
            id=data["id"],
            name=data["name"],
            project_path=data["project_path"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            checkpoints=[Checkpoint.from_dict(cp) for cp in data.get("checkpoints", [])],
        )

    def save_metadata(self) -> None:
        """Save session metadata to session.json."""
        if not self._session_dir:
            return
        
        self.updated_at = datetime.now().isoformat()
        metadata_file = self._session_dir / "session.json"
        metadata_file.write_text(json.dumps(self.to_dict(), indent=2))

    def create_checkpoint(
        self,
        message: str,
        conversation_state: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Create a new checkpoint with the current state."""
        checkpoint = Checkpoint(
            number=len(self.checkpoints) + 1,
            message=message,
            timestamp=datetime.now().isoformat(),
        )
        self.checkpoints.append(checkpoint)
        
        # Save checkpoint state
        if self._session_dir and conversation_state:
            checkpoint_dir = self._session_dir / "checkpoints"
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            
            checkpoint_file = checkpoint_dir / f"{checkpoint.number}.json"
            checkpoint_file.write_text(json.dumps(conversation_state, indent=2, default=str))
        
        # Update session metadata
        self.save_metadata()
        
        return checkpoint

    def load_checkpoint(self, number: int) -> dict[str, Any] | None:
        """Load a checkpoint's state."""
        if not self._session_dir:
            return None
        
        checkpoint_file = self._session_dir / "checkpoints" / f"{number}.json"
        if checkpoint_file.exists():
            return json.loads(checkpoint_file.read_text())
        return None

    def rewind_to(self, number: int) -> tuple[bool, str, dict[str, Any] | None]:
        """Rewind to a specific checkpoint number.
        
        Returns: (success, message, state)
        """
        if number < 1 or number > len(self.checkpoints):
            return False, f"Invalid checkpoint {number}. Range: 1-{len(self.checkpoints)}", None
        
        # Load the target checkpoint
        state = self.load_checkpoint(number)
        if state is None:
            return False, f"Could not load checkpoint {number}", None
        
        # Remove checkpoints after the target
        for i in range(number + 1, len(self.checkpoints) + 1):
            checkpoint_file = self._session_dir / "checkpoints" / f"{i}.json" if self._session_dir else None
            if checkpoint_file and checkpoint_file.exists():
                checkpoint_file.unlink()
        
        self.checkpoints = self.checkpoints[:number]
        self.save_metadata()
        
        target = self.checkpoints[number - 1]
        return True, f"Rewound to checkpoint {number}: {target.message}", state


class SessionManager:
    """Manages sessions stored in ~/.lizcode/sessions/."""

    def __init__(self, lizcode_dir: Path | None = None):
        self.lizcode_dir = lizcode_dir or (Path.home() / ".lizcode")
        self.sessions_dir = self.lizcode_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_session: Session | None = None

    def create_session(self, project_path: Path, name: str = "New Session") -> Session:
        """Create a new session."""
        session = Session.create(project_path, name)
        
        session_dir = self.sessions_dir / session.id
        session.set_session_dir(session_dir)
        session.save_metadata()
        
        # Create subdirectories
        (session_dir / "checkpoints").mkdir(exist_ok=True)
        
        # Initialize empty files
        (session_dir / "conversation.json").write_text("[]")
        (session_dir / "tasks.json").write_text('{"tasks": []}')
        
        self.current_session = session
        return session

    def load_session(self, session_id: str) -> Session | None:
        """Load a session by ID."""
        session_dir = self.sessions_dir / session_id
        metadata_file = session_dir / "session.json"
        
        if not metadata_file.exists():
            return None
        
        data = json.loads(metadata_file.read_text())
        session = Session.from_dict(data)
        session.set_session_dir(session_dir)
        
        self.current_session = session
        return session

    def list_sessions(self, project_path: Path | None = None) -> list[Session]:
        """List all sessions, optionally filtered by project path."""
        sessions = []
        
        for session_dir in self.sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            metadata_file = session_dir / "session.json"
            if not metadata_file.exists():
                continue
            
            try:
                data = json.loads(metadata_file.read_text())
                session = Session.from_dict(data)
                session.set_session_dir(session_dir)
                
                # Filter by project path if specified
                if project_path is None or session.project_path == str(project_path.resolve()):
                    sessions.append(session)
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Sort by updated_at descending (most recent first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def get_most_recent_session(self, project_path: Path) -> Session | None:
        """Get the most recent session for a project."""
        sessions = self.list_sessions(project_path)
        return sessions[0] if sessions else None

    def save_conversation(self, conversation_state: dict[str, Any]) -> None:
        """Save conversation state to current session."""
        if not self.current_session or not self.current_session.session_dir:
            return
        
        conv_file = self.current_session.session_dir / "conversation.json"
        conv_file.write_text(json.dumps(conversation_state, indent=2, default=str))

    def load_conversation(self) -> dict[str, Any] | None:
        """Load conversation state from current session."""
        if not self.current_session or not self.current_session.session_dir:
            return None
        
        conv_file = self.current_session.session_dir / "conversation.json"
        if conv_file.exists():
            return json.loads(conv_file.read_text())
        return None

    def save_tasks(self, tasks_state: dict[str, Any]) -> None:
        """Save tasks state to current session."""
        if not self.current_session or not self.current_session.session_dir:
            return
        
        tasks_file = self.current_session.session_dir / "tasks.json"
        tasks_file.write_text(json.dumps(tasks_state, indent=2, default=str))

    def load_tasks(self) -> dict[str, Any] | None:
        """Load tasks state from current session."""
        if not self.current_session or not self.current_session.session_dir:
            return None
        
        tasks_file = self.current_session.session_dir / "tasks.json"
        if tasks_file.exists():
            return json.loads(tasks_file.read_text())
        return None
