"""Subagent system for LizCode.

Subagents are separate workers that run their own LLM conversations
with specialized tools and prompts. They can run:
- In parallel (async workers, same process)
- In background (subprocess, for long-running tasks)
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from lizcode.core.providers.base import Provider


class SubagentType(Enum):
    """Types of specialized subagents."""

    EXPLORE = "explore"  # Codebase exploration - read-only
    PLAN = "plan"  # Design and planning - read-only
    TEST_RUNNER = "test_runner"  # Run tests
    BUILD_VALIDATOR = "build_validator"  # Check builds
    CODE_REVIEWER = "code_reviewer"  # Review code changes

    def __str__(self) -> str:
        return self.value


# Tool restrictions per subagent type
SUBAGENT_TOOLS = {
    SubagentType.EXPLORE: ["read_file", "glob", "grep", "list_files"],
    SubagentType.PLAN: ["read_file", "glob", "grep", "list_files"],
    SubagentType.TEST_RUNNER: ["read_file", "glob", "grep", "list_files", "bash"],
    SubagentType.BUILD_VALIDATOR: ["read_file", "glob", "grep", "list_files", "bash"],
    SubagentType.CODE_REVIEWER: ["read_file", "glob", "grep", "list_files"],
}

# System prompts for each subagent type
SUBAGENT_PROMPTS = {
    SubagentType.EXPLORE: """\
You are an Explore subagent for LizCode. Your job is to thoroughly explore and understand a codebase.

Your capabilities:
- Read files to understand code
- Search for patterns with grep
- Find files with glob
- List directory contents

Your task:
1. Explore the codebase systematically
2. Identify relevant files and patterns
3. Understand the architecture and structure
4. Report back with findings

Be thorough but focused. Report:
- Key files discovered
- Patterns and conventions used
- Architecture observations
- Anything relevant to the parent agent's query

You CANNOT modify files. You are read-only.
""",

    SubagentType.PLAN: """\
You are a Plan subagent for LizCode. Your job is to design implementation approaches.

Your capabilities:
- Read files to understand existing code
- Search for patterns to understand conventions
- Analyze architecture

Your task:
1. Understand the requirements given to you
2. Explore the relevant code
3. Design an implementation approach
4. Consider alternatives
5. Report back with a detailed plan

Your output should include:
- Recommended approach with rationale
- Files that need to be modified
- Step-by-step implementation plan
- Potential risks or concerns
- Verification steps

You CANNOT modify files. You are read-only.
""",

    SubagentType.TEST_RUNNER: """\
You are a Test Runner subagent for LizCode. Your job is to run tests and report results.

Your capabilities:
- Read test files
- Execute test commands
- Analyze test output

Your task:
1. Identify the test framework and commands
2. Run the tests
3. Parse the results
4. Report failures clearly

Report:
- Overall pass/fail status
- Number of tests run/passed/failed
- Details of any failures
- Suggestions for fixes if obvious
""",

    SubagentType.BUILD_VALIDATOR: """\
You are a Build Validator subagent for LizCode. Your job is to validate that code builds correctly.

Your capabilities:
- Read configuration files
- Execute build commands
- Analyze build output

Your task:
1. Identify the build system
2. Run the build
3. Check for errors or warnings
4. Report the results

Report:
- Build success/failure
- Any errors with file/line info
- Warnings that might be concerning
- Build artifacts produced
""",

    SubagentType.CODE_REVIEWER: """\
You are a Code Review subagent for LizCode. Your job is to review code for issues.

Your capabilities:
- Read code files
- Search for patterns
- Analyze code quality

Your task:
1. Review the specified code
2. Check for bugs, security issues, style problems
3. Suggest improvements

Report:
- Issues found (categorized by severity)
- Suggestions for improvement
- Overall assessment
""",
}


@dataclass
class SubagentResult:
    """Result from a subagent execution."""

    agent_id: str
    agent_type: SubagentType
    prompt: str
    result: str
    success: bool
    duration_seconds: float
    output_file: Path | None = None  # For background agents
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "prompt": self.prompt,
            "result": self.result,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "output_file": str(self.output_file) if self.output_file else None,
            "error": self.error,
        }


@dataclass
class SubagentManager:
    """Manages subagent spawning and execution."""

    provider_factory: Any  # Callable to create provider
    working_directory: Path = field(default_factory=Path.cwd)
    output_dir: Path = field(default_factory=lambda: Path(".lizcode/subagents"))

    # Track running background agents
    _background_processes: dict[str, multiprocessing.Process] = field(default_factory=dict)

    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def spawn(
        self,
        agent_type: SubagentType,
        prompt: str,
        run_in_background: bool = False,
    ) -> SubagentResult:
        """Spawn a subagent.
        
        Args:
            agent_type: Type of agent to spawn
            prompt: The task/query for the agent
            run_in_background: If True, spawns as subprocess and returns immediately
            
        Returns:
            SubagentResult with the agent's findings
        """
        agent_id = str(uuid4())[:8]
        start_time = datetime.now()

        if run_in_background:
            return await self._spawn_background(agent_id, agent_type, prompt)
        else:
            return await self._spawn_async(agent_id, agent_type, prompt)

    async def spawn_parallel(
        self,
        tasks: list[tuple[SubagentType, str]],
    ) -> list[SubagentResult]:
        """Spawn multiple subagents in parallel.
        
        Args:
            tasks: List of (agent_type, prompt) tuples
            
        Returns:
            List of results in same order as input
        """
        coroutines = [
            self._spawn_async(str(uuid4())[:8], agent_type, prompt)
            for agent_type, prompt in tasks
        ]
        return await asyncio.gather(*coroutines)

    async def _spawn_async(
        self,
        agent_id: str,
        agent_type: SubagentType,
        prompt: str,
    ) -> SubagentResult:
        """Spawn an async subagent (same process, concurrent)."""
        start_time = datetime.now()

        try:
            # Create a provider for this subagent
            provider = self.provider_factory()

            # Get the restricted tools for this agent type
            from lizcode.tools import create_tool_registry
            
            registry = create_tool_registry()
            allowed_tools = SUBAGENT_TOOLS.get(agent_type, [])

            # Filter to only allowed tools
            tools = [
                tool for tool in registry.get_all()
                if tool.name in allowed_tools
            ]

            # Build messages
            system_prompt = SUBAGENT_PROMPTS.get(agent_type, "You are a helpful assistant.")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            # Run the subagent conversation loop
            result_text = ""
            max_iterations = 10  # Prevent infinite loops

            for _ in range(max_iterations):
                response = await provider.chat(messages, tools=tools if tools else None)

                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])

                if content:
                    result_text += content

                if not tool_calls:
                    break

                # Execute tools
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]),
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                for tc in tool_calls:
                    tool = registry.get(tc["name"])
                    if tool and tool.name in allowed_tools:
                        try:
                            tool_result = await tool.execute(**tc["arguments"])
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": str(tool_result),
                            })
                        except Exception as e:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": f"Error: {e}",
                            })
                    else:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": f"Tool not allowed: {tc['name']}",
                        })

            await provider.close()

            duration = (datetime.now() - start_time).total_seconds()

            return SubagentResult(
                agent_id=agent_id,
                agent_type=agent_type,
                prompt=prompt,
                result=result_text,
                success=True,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return SubagentResult(
                agent_id=agent_id,
                agent_type=agent_type,
                prompt=prompt,
                result="",
                success=False,
                duration_seconds=duration,
                error=str(e),
            )

    async def _spawn_background(
        self,
        agent_id: str,
        agent_type: SubagentType,
        prompt: str,
    ) -> SubagentResult:
        """Spawn a background subprocess agent."""
        output_file = self.output_dir / f"{agent_id}.txt"
        
        # Write initial status
        output_file.write_text(f"[{datetime.now().isoformat()}] Starting {agent_type.value} agent...\n")

        # Spawn subprocess
        process = multiprocessing.Process(
            target=_run_background_agent,
            args=(
                agent_id,
                agent_type.value,
                prompt,
                str(output_file),
                str(self.working_directory),
            ),
        )
        process.start()
        self._background_processes[agent_id] = process

        # Return immediately with output file path
        return SubagentResult(
            agent_id=agent_id,
            agent_type=agent_type,
            prompt=prompt,
            result=f"Background agent started. Monitor output at: {output_file}",
            success=True,
            duration_seconds=0.0,
            output_file=output_file,
        )

    def check_background_agent(self, agent_id: str) -> dict[str, Any]:
        """Check status of a background agent."""
        process = self._background_processes.get(agent_id)
        output_file = self.output_dir / f"{agent_id}.txt"

        if not process:
            return {"status": "not_found", "agent_id": agent_id}

        is_running = process.is_alive()
        output = output_file.read_text() if output_file.exists() else ""

        return {
            "status": "running" if is_running else "completed",
            "agent_id": agent_id,
            "output": output,
        }

    def resume_agent(self, agent_id: str, additional_prompt: str) -> None:
        """Resume a completed agent with additional context.
        
        Note: This would require saving/loading conversation state.
        For MVP, we just start a new agent with context from the previous.
        """
        # Load previous output
        output_file = self.output_dir / f"{agent_id}.txt"
        if not output_file.exists():
            raise ValueError(f"No output found for agent {agent_id}")

        previous_output = output_file.read_text()
        
        # Create new prompt with context
        new_prompt = f"""Previous agent context:
{previous_output}

Continue with:
{additional_prompt}
"""
        return new_prompt


def _run_background_agent(
    agent_id: str,
    agent_type_str: str,
    prompt: str,
    output_file: str,
    working_directory: str,
):
    """Run agent in subprocess. This is the target for multiprocessing."""
    import asyncio
    
    # Change to working directory
    os.chdir(working_directory)
    
    output_path = Path(output_file)
    agent_type = SubagentType(agent_type_str)

    def log(message: str):
        with open(output_path, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")

    async def run():
        log(f"Agent {agent_id} ({agent_type.value}) starting...")
        log(f"Prompt: {prompt[:200]}...")

        try:
            # Import here to avoid circular imports
            from lizcode.config.settings import Settings
            from lizcode.core.providers.openrouter import OpenRouterProvider
            from lizcode.core.providers.ollama import OllamaProvider
            from lizcode.tools import create_tool_registry

            settings = Settings.load_from_yaml()

            # Create provider
            if settings.provider == "openrouter":
                provider = OpenRouterProvider(
                    api_key=settings.openrouter_api_key,
                    model=settings.openrouter_model,
                )
            else:
                provider = OllamaProvider(
                    model=settings.ollama_model,
                    host=settings.ollama_host,
                )

            # Get tools
            registry = create_tool_registry()
            allowed_tools = SUBAGENT_TOOLS.get(agent_type, [])
            tools = [t for t in registry.get_all() if t.name in allowed_tools]

            # Build messages
            system_prompt = SUBAGENT_PROMPTS.get(agent_type, "")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            # Conversation loop
            max_iterations = 15
            for iteration in range(max_iterations):
                log(f"Iteration {iteration + 1}...")

                response = await provider.chat(messages, tools=tools if tools else None)

                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])

                if content:
                    log(f"Response: {content}")

                if not tool_calls:
                    break

                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]),
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                for tc in tool_calls:
                    tool_name = tc["name"]
                    log(f"Calling tool: {tool_name}")

                    tool = registry.get(tool_name)
                    if tool and tool.name in allowed_tools:
                        try:
                            result = await tool.execute(**tc["arguments"])
                            result_str = str(result)
                            # Truncate for logging
                            log_result = result_str[:500] + "..." if len(result_str) > 500 else result_str
                            log(f"Tool result: {log_result}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": result_str,
                            })
                        except Exception as e:
                            log(f"Tool error: {e}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": f"Error: {e}",
                            })
                    else:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": f"Tool not allowed: {tool_name}",
                        })

            await provider.close()
            log("Agent completed successfully.")

        except Exception as e:
            log(f"Agent failed with error: {e}")
            import traceback
            log(traceback.format_exc())

    asyncio.run(run())
