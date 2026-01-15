"""Plan file management for LizCode."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class PlanPhase(Enum):
    """Phases of the planning workflow."""

    INITIAL_UNDERSTANDING = "initial_understanding"
    DESIGN = "design"
    REVIEW = "review"
    FINAL_PLAN = "final_plan"
    READY_TO_EXECUTE = "ready_to_execute"

    def __str__(self) -> str:
        return self.value


@dataclass
class PlanStep:
    """A single step in the implementation plan."""

    description: str
    files_involved: list[str] = field(default_factory=list)
    estimated_complexity: str = "medium"  # low, medium, high
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "files_involved": self.files_involved,
            "estimated_complexity": self.estimated_complexity,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        return cls(
            description=data["description"],
            files_involved=data.get("files_involved", []),
            estimated_complexity=data.get("estimated_complexity", "medium"),
            notes=data.get("notes", ""),
        )


@dataclass
class Plan:
    """A complete implementation plan."""

    title: str
    objective: str
    phase: PlanPhase = PlanPhase.INITIAL_UNDERSTANDING
    
    # Phase 1: Understanding
    context_gathered: list[str] = field(default_factory=list)  # Files/patterns explored
    questions_asked: list[str] = field(default_factory=list)
    questions_answered: dict[str, str] = field(default_factory=dict)
    
    # Phase 2: Design
    approach: str = ""
    alternatives_considered: list[str] = field(default_factory=list)
    chosen_approach_rationale: str = ""
    
    # Phase 3: Review
    critical_files: list[str] = field(default_factory=list)
    potential_risks: list[str] = field(default_factory=list)
    
    # Phase 4: Final plan
    steps: list[PlanStep] = field(default_factory=list)
    verification_steps: list[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    _persist_path: Path | None = field(default=None, repr=False)

    def advance_phase(self) -> None:
        """Move to the next phase."""
        phases = list(PlanPhase)
        current_idx = phases.index(self.phase)
        if current_idx < len(phases) - 1:
            self.phase = phases[current_idx + 1]
            self.updated_at = datetime.now()
            self._persist()

    def add_context(self, context: str) -> None:
        """Add explored context."""
        self.context_gathered.append(context)
        self.updated_at = datetime.now()
        self._persist()

    def add_question(self, question: str) -> None:
        """Add a question to ask the user."""
        self.questions_asked.append(question)
        self.updated_at = datetime.now()
        self._persist()

    def answer_question(self, question: str, answer: str) -> None:
        """Record an answer to a question."""
        self.questions_answered[question] = answer
        self.updated_at = datetime.now()
        self._persist()

    def set_approach(self, approach: str, rationale: str = "") -> None:
        """Set the chosen approach."""
        self.approach = approach
        self.chosen_approach_rationale = rationale
        self.updated_at = datetime.now()
        self._persist()

    def add_alternative(self, alternative: str) -> None:
        """Add an alternative approach that was considered."""
        self.alternatives_considered.append(alternative)
        self.updated_at = datetime.now()
        self._persist()

    def add_critical_file(self, file_path: str) -> None:
        """Add a file that needs to be modified."""
        if file_path not in self.critical_files:
            self.critical_files.append(file_path)
            self.updated_at = datetime.now()
            self._persist()

    def add_risk(self, risk: str) -> None:
        """Add a potential risk."""
        self.potential_risks.append(risk)
        self.updated_at = datetime.now()
        self._persist()

    def add_step(self, step: PlanStep) -> None:
        """Add an implementation step."""
        self.steps.append(step)
        self.updated_at = datetime.now()
        self._persist()

    def add_verification(self, verification: str) -> None:
        """Add a verification step."""
        self.verification_steps.append(verification)
        self.updated_at = datetime.now()
        self._persist()

    def to_markdown(self) -> str:
        """Convert plan to markdown format."""
        lines = [
            f"# {self.title}",
            "",
            f"**Phase:** {self.phase.value}",
            f"**Created:** {self.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"**Updated:** {self.updated_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Objective",
            self.objective,
            "",
        ]

        if self.context_gathered:
            lines.extend([
                "## Context Gathered",
                "",
            ])
            for ctx in self.context_gathered:
                lines.append(f"- {ctx}")
            lines.append("")

        if self.questions_asked:
            lines.extend([
                "## Questions",
                "",
            ])
            for q in self.questions_asked:
                answer = self.questions_answered.get(q, "_Unanswered_")
                lines.append(f"**Q:** {q}")
                lines.append(f"**A:** {answer}")
                lines.append("")

        if self.approach:
            lines.extend([
                "## Chosen Approach",
                self.approach,
                "",
            ])
            if self.chosen_approach_rationale:
                lines.extend([
                    "### Rationale",
                    self.chosen_approach_rationale,
                    "",
                ])

        if self.alternatives_considered:
            lines.extend([
                "## Alternatives Considered",
                "",
            ])
            for alt in self.alternatives_considered:
                lines.append(f"- {alt}")
            lines.append("")

        if self.critical_files:
            lines.extend([
                "## Critical Files",
                "",
            ])
            for f in self.critical_files:
                lines.append(f"- `{f}`")
            lines.append("")

        if self.potential_risks:
            lines.extend([
                "## Potential Risks",
                "",
            ])
            for risk in self.potential_risks:
                lines.append(f"- {risk}")
            lines.append("")

        if self.steps:
            lines.extend([
                "## Implementation Steps",
                "",
            ])
            for i, step in enumerate(self.steps, 1):
                lines.append(f"### Step {i}: {step.description}")
                if step.files_involved:
                    lines.append(f"**Files:** {', '.join(f'`{f}`' for f in step.files_involved)}")
                lines.append(f"**Complexity:** {step.estimated_complexity}")
                if step.notes:
                    lines.append(f"**Notes:** {step.notes}")
                lines.append("")

        if self.verification_steps:
            lines.extend([
                "## Verification",
                "",
            ])
            for v in self.verification_steps:
                lines.append(f"- [ ] {v}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "objective": self.objective,
            "phase": self.phase.value,
            "context_gathered": self.context_gathered,
            "questions_asked": self.questions_asked,
            "questions_answered": self.questions_answered,
            "approach": self.approach,
            "alternatives_considered": self.alternatives_considered,
            "chosen_approach_rationale": self.chosen_approach_rationale,
            "critical_files": self.critical_files,
            "potential_risks": self.potential_risks,
            "steps": [s.to_dict() for s in self.steps],
            "verification_steps": self.verification_steps,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        """Create from dictionary."""
        plan = cls(
            title=data["title"],
            objective=data["objective"],
            phase=PlanPhase(data["phase"]),
            context_gathered=data.get("context_gathered", []),
            questions_asked=data.get("questions_asked", []),
            questions_answered=data.get("questions_answered", {}),
            approach=data.get("approach", ""),
            alternatives_considered=data.get("alternatives_considered", []),
            chosen_approach_rationale=data.get("chosen_approach_rationale", ""),
            critical_files=data.get("critical_files", []),
            potential_risks=data.get("potential_risks", []),
            steps=[PlanStep.from_dict(s) for s in data.get("steps", [])],
            verification_steps=data.get("verification_steps", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        return plan

    def set_persist_path(self, path: Path) -> None:
        """Set path for auto-persistence."""
        self._persist_path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def _persist(self) -> None:
        """Save to disk."""
        if self._persist_path:
            # Save both markdown and JSON
            md_path = self._persist_path.with_suffix(".md")
            json_path = self._persist_path.with_suffix(".json")
            
            md_path.write_text(self.to_markdown())
            json_path.write_text(json.dumps(self.to_dict(), indent=2, default=str))

    @classmethod
    def load(cls, path: Path) -> Plan | None:
        """Load plan from JSON file."""
        json_path = path.with_suffix(".json")
        if not json_path.exists():
            return None

        data = json.loads(json_path.read_text())
        plan = cls.from_dict(data)
        plan.set_persist_path(path)
        return plan

    @classmethod
    def create(cls, title: str, objective: str, persist_path: Path) -> Plan:
        """Create a new plan."""
        plan = cls(title=title, objective=objective)
        plan.set_persist_path(persist_path)
        plan._persist()
        return plan

    def to_tasks(self) -> list[dict[str, str]]:
        """Convert plan steps to task list format.
        
        Note: Verification steps are NOT included as tasks.
        They remain in plan.md for human reference but are not
        actionable by the model (e.g., "run app and verify gliders work"
        requires human judgment).
        """
        tasks = []
        for step in self.steps:
            # Create imperative and active forms
            content = step.description
            # Simple heuristic for active form
            if content.startswith("Add"):
                active = content.replace("Add", "Adding", 1)
            elif content.startswith("Create"):
                active = content.replace("Create", "Creating", 1)
            elif content.startswith("Update"):
                active = content.replace("Update", "Updating", 1)
            elif content.startswith("Fix"):
                active = content.replace("Fix", "Fixing", 1)
            elif content.startswith("Implement"):
                active = content.replace("Implement", "Implementing", 1)
            elif content.startswith("Remove"):
                active = content.replace("Remove", "Removing", 1)
            elif content.startswith("Refactor"):
                active = content.replace("Refactor", "Refactoring", 1)
            else:
                active = f"Working on: {content}"

            tasks.append({
                "content": content,
                "active_form": active,
                "metadata": {
                    "files": step.files_involved,
                    "complexity": step.estimated_complexity,
                },
            })

        # Verification steps are NOT added as tasks
        # They stay in plan.md for human reference only

        return tasks
