"""Skill/slash command system for LizCode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from lizcode.tools.base import Permission, Tool, ToolResult


@dataclass
class Skill:
    """A skill/slash command definition."""

    name: str
    description: str
    handler: Callable[[str], str] | None = None  # Args -> Result
    prompt_template: str = ""  # Template for AI to follow


# Built-in skills
BUILTIN_SKILLS: dict[str, Skill] = {
    "commit": Skill(
        name="commit",
        description="Create a git commit with generated message",
        prompt_template="""Generate a git commit for the staged changes.

1. Run `git diff --cached` to see staged changes
2. Analyze the changes and generate a commit message following conventional commits:
   - feat: new feature
   - fix: bug fix
   - docs: documentation
   - style: formatting
   - refactor: code restructure
   - test: tests
   - chore: maintenance
3. Run `git commit -m "<message>"`
4. Report the result""",
    ),
    "review-pr": Skill(
        name="review-pr",
        description="Review a pull request",
        prompt_template="""Review the pull request.

1. Use `git log --oneline origin/main..HEAD` to see commits
2. Use `git diff origin/main` to see all changes
3. Analyze:
   - Code quality
   - Potential bugs
   - Security issues
   - Test coverage
   - Documentation
4. Provide structured feedback""",
    ),
    "init": Skill(
        name="init",
        description="Initialize a new project with best practices",
        prompt_template="""Initialize a new project.

1. Ask what type of project (Python, Node, etc.)
2. Create appropriate structure:
   - README.md
   - .gitignore
   - License
   - Config files
3. Initialize git if not already done
4. Set up development environment""",
    ),
    "test": Skill(
        name="test",
        description="Run tests and analyze results",
        prompt_template="""Run tests for this project.

1. Detect the test framework (pytest, jest, etc.)
2. Run the tests
3. Analyze failures if any
4. Suggest fixes for failing tests""",
    ),
    "lint": Skill(
        name="lint",
        description="Run linters and formatters",
        prompt_template="""Run linting and formatting.

1. Detect available linters (ruff, eslint, etc.)
2. Run linters
3. Report issues
4. Ask if should auto-fix""",
    ),
    "docs": Skill(
        name="docs",
        description="Generate or update documentation",
        prompt_template="""Generate documentation.

1. Analyze the codebase structure
2. Generate/update README.md
3. Add docstrings where missing
4. Generate API documentation if applicable""",
    ),
}


class SkillTool(Tool):
    """Execute slash commands/skills."""

    name = "skill"
    description = """Execute a slash command skill.

Available skills:
- /commit: Create git commit with generated message
- /review-pr: Review a pull request
- /init: Initialize a new project
- /test: Run and analyze tests
- /lint: Run linters and formatters
- /docs: Generate documentation

When user says "/commit" or "run /commit", use this tool."""

    permission = Permission.READ  # Skills themselves may trigger other tools

    def __init__(self):
        self._skills = BUILTIN_SKILLS.copy()
        self._custom_skills: dict[str, Skill] = {}

    def register_skill(self, skill: Skill) -> None:
        """Register a custom skill."""
        self._custom_skills[skill.name] = skill

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name."""
        # Remove leading slash if present
        name = name.lstrip("/")
        return self._custom_skills.get(name) or self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        """List all available skills."""
        all_skills = {**self._skills, **self._custom_skills}
        return list(all_skills.values())

    @property
    def parameters(self) -> dict[str, Any]:
        skill_names = list(self._skills.keys()) + list(self._custom_skills.keys())
        return {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": f"Skill name to execute. Available: {', '.join(skill_names)}",
                },
                "args": {
                    "type": "string",
                    "description": "Optional arguments for the skill",
                },
            },
            "required": ["skill"],
        }

    async def execute(
        self,
        skill: str,
        args: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a skill."""
        skill_def = self.get_skill(skill)

        if not skill_def:
            available = ", ".join(self._skills.keys())
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown skill: {skill}. Available: {available}",
            )

        # If skill has a handler, run it directly
        if skill_def.handler:
            try:
                result = skill_def.handler(args)
                return ToolResult(success=True, output=result)
            except Exception as e:
                return ToolResult(success=False, output="", error=f"Skill error: {e}")

        # Return the prompt template for the AI to follow
        output = f"## Skill: /{skill_def.name}\n\n"
        output += f"{skill_def.description}\n\n"
        output += "### Instructions:\n"
        output += skill_def.prompt_template

        if args:
            output += f"\n\n### Arguments: {args}"

        return ToolResult(success=True, output=output)
