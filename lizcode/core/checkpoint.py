"""Checkpoint system for LizCode - git-based session management."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    """A single checkpoint."""

    number: int
    commit_hash: str
    message: str
    timestamp: str
    conversation_file: Path | None = None


@dataclass
class CheckpointManager:
    """Manages git-based checkpoints for LizCode sessions."""

    working_dir: Path
    branch_name: str | None = None
    original_branch: str | None = None
    checkpoints: list[Checkpoint] = field(default_factory=list)
    _initialized: bool = False

    def _run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command."""
        return subprocess.run(
            ["git", *args],
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            check=check,
        )

    def _is_git_repo(self) -> bool:
        """Check if we're in a git repository."""
        result = self._run_git("rev-parse", "--git-dir", check=False)
        return result.returncode == 0

    def _get_current_branch(self) -> str:
        """Get current branch name."""
        result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def _has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        result = self._run_git("status", "--porcelain")
        return bool(result.stdout.strip())

    def _slugify(self, text: str) -> str:
        """Convert text to branch-safe slug."""
        # Lowercase and replace spaces with hyphens
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')
        # Limit length
        return slug[:50] if slug else "session"

    def initialize(self, slug: str | None = None) -> bool:
        """Initialize checkpoint system.
        
        Creates a new branch like: lizcode/fix-auth-bug
        
        Args:
            slug: Pre-generated branch slug (from LLM). If None, uses "session".
        """
        if self._initialized:
            return True

        if not self._is_git_repo():
            return False

        self.original_branch = self._get_current_branch()

        # Check if already on a lizcode branch
        if self.original_branch.startswith("lizcode/"):
            self.branch_name = self.original_branch
            self._initialized = True
            self._load_checkpoints()
            return True

        # Use provided slug or default
        slug = self._slugify(slug) if slug else "session"
        self.branch_name = f"lizcode/{slug}"

        # Check if branch exists, add suffix if needed
        result = self._run_git("branch", "--list", self.branch_name, check=False)
        if result.stdout.strip():
            timestamp = datetime.now().strftime("%H%M")
            self.branch_name = f"lizcode/{slug}-{timestamp}"

        # Create and checkout new branch
        try:
            self._run_git("checkout", "-b", self.branch_name)
            self._initialized = True

            # Create checkpoints directory
            checkpoint_dir = self.working_dir / ".lizcode" / "checkpoints"
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

            return True
        except subprocess.CalledProcessError:
            return False

    def _load_checkpoints(self) -> None:
        """Load existing checkpoints from git log."""
        if not self.branch_name:
            return

        # Get commits on this branch with [lizcode] prefix
        try:
            result = self._run_git(
                "log",
                "--oneline",
                "--grep=\\[lizcode\\]",
                "--format=%H|%s|%ai",
            )
            self.checkpoints = []
            for i, line in enumerate(reversed(result.stdout.strip().split("\n"))):
                if not line:
                    continue
                parts = line.split("|", 2)
                if len(parts) >= 2:
                    self.checkpoints.append(Checkpoint(
                        number=i + 1,
                        commit_hash=parts[0],
                        message=parts[1].replace("[lizcode] ", ""),
                        timestamp=parts[2] if len(parts) > 2 else "",
                    ))
        except subprocess.CalledProcessError:
            pass

    def create_checkpoint(
        self,
        message: str,
        conversation_state: dict[str, Any] | None = None,
    ) -> Checkpoint | None:
        """Create a new checkpoint (git commit).
        
        Called after each user-AI interaction completes.
        """
        if not self._initialized or not self.branch_name:
            return None

        if not self._has_changes():
            # Still save conversation state even without file changes
            if conversation_state:
                self._save_conversation_state(len(self.checkpoints) + 1, conversation_state)
            return None

        # Stage all changes
        self._run_git("add", "-A")

        # Create commit with [lizcode] prefix
        commit_message = f"[lizcode] {message}"
        try:
            self._run_git("commit", "-m", commit_message)
        except subprocess.CalledProcessError as e:
            # Commit failed (maybe nothing to commit)
            return None

        # Get the commit hash
        result = self._run_git("rev-parse", "HEAD")
        commit_hash = result.stdout.strip()

        # Create checkpoint object
        checkpoint = Checkpoint(
            number=len(self.checkpoints) + 1,
            commit_hash=commit_hash,
            message=message,
            timestamp=datetime.now().isoformat(),
        )
        self.checkpoints.append(checkpoint)

        # Save conversation state
        if conversation_state:
            checkpoint.conversation_file = self._save_conversation_state(
                checkpoint.number,
                conversation_state,
            )

        return checkpoint

    def _save_conversation_state(
        self,
        checkpoint_num: int,
        conversation_state: dict[str, Any],
    ) -> Path:
        """Save conversation state to JSON file."""
        checkpoint_dir = self.working_dir / ".lizcode" / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        state_file = checkpoint_dir / f"{checkpoint_num}.json"
        state_file.write_text(json.dumps(conversation_state, indent=2, default=str))

        return state_file

    def _load_conversation_state(self, checkpoint_num: int) -> dict[str, Any] | None:
        """Load conversation state from checkpoint."""
        state_file = self.working_dir / ".lizcode" / "checkpoints" / f"{checkpoint_num}.json"
        if state_file.exists():
            return json.loads(state_file.read_text())
        return None

    def rewind(self, count: int = 1) -> tuple[bool, str, dict[str, Any] | None]:
        """Rewind N checkpoints.
        
        Returns: (success, message, conversation_state)
        """
        if not self._initialized:
            return False, "Checkpoint system not initialized", None

        if count < 1:
            return False, "Count must be at least 1", None

        if count > len(self.checkpoints):
            return False, f"Only {len(self.checkpoints)} checkpoints available", None

        target_checkpoint_num = len(self.checkpoints) - count
        target_checkpoint = self.checkpoints[target_checkpoint_num - 1] if target_checkpoint_num > 0 else None

        if target_checkpoint:
            # Reset to target checkpoint
            try:
                self._run_git("reset", "--hard", target_checkpoint.commit_hash)
            except subprocess.CalledProcessError as e:
                return False, f"Git reset failed: {e.stderr}", None

            # Load conversation state
            conv_state = self._load_conversation_state(target_checkpoint.number)

            # Remove rewound checkpoints from list
            self.checkpoints = self.checkpoints[:target_checkpoint_num]

            # Delete checkpoint files for rewound checkpoints
            for i in range(target_checkpoint_num + 1, target_checkpoint_num + count + 1):
                state_file = self.working_dir / ".lizcode" / "checkpoints" / f"{i}.json"
                if state_file.exists():
                    state_file.unlink()

            return True, f"Rewound to checkpoint {target_checkpoint.number}: {target_checkpoint.message}", conv_state
        else:
            # Rewind to before first checkpoint (start of branch)
            try:
                # Get the parent of the first checkpoint
                if self.original_branch:
                    self._run_git("reset", "--hard", f"{self.original_branch}")
                else:
                    # Just reset to first commit
                    first_hash = self.checkpoints[0].commit_hash if self.checkpoints else None
                    if first_hash:
                        self._run_git("reset", "--hard", f"{first_hash}~1")
            except subprocess.CalledProcessError:
                pass

            self.checkpoints = []

            # Delete all checkpoint files
            checkpoint_dir = self.working_dir / ".lizcode" / "checkpoints"
            for f in checkpoint_dir.glob("*.json"):
                f.unlink()

            return True, "Rewound to start of session", None

    def list_checkpoints(self) -> list[Checkpoint]:
        """List all checkpoints in current session."""
        return self.checkpoints

    def merge_to_original(self, squash: bool = False) -> tuple[bool, str]:
        """Merge the lizcode branch back to original branch.
        
        Returns: (success, message)
        """
        if not self._initialized or not self.original_branch or not self.branch_name:
            return False, "Cannot merge: session not properly initialized"

        if self.original_branch == self.branch_name:
            return False, "Cannot merge: already on original branch"

        try:
            # Checkout original branch
            self._run_git("checkout", self.original_branch)

            if squash:
                # Squash merge (single commit)
                self._run_git("merge", "--squash", self.branch_name)
                self._run_git("commit", "-m", f"Merge {self.branch_name} (squashed)")
            else:
                # Regular merge
                self._run_git("merge", self.branch_name)

            # Optionally delete the lizcode branch
            # self._run_git("branch", "-d", self.branch_name)

            return True, f"Merged {self.branch_name} into {self.original_branch}"
        except subprocess.CalledProcessError as e:
            # Try to recover
            self._run_git("checkout", self.branch_name, check=False)
            return False, f"Merge failed: {e.stderr}"

    def get_status(self) -> dict[str, Any]:
        """Get current checkpoint status."""
        return {
            "initialized": self._initialized,
            "branch": self.branch_name,
            "original_branch": self.original_branch,
            "checkpoint_count": len(self.checkpoints),
            "has_changes": self._has_changes() if self._initialized else False,
        }
