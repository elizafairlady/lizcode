"""Bash command execution tool for LizCode."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from lizcode.tools.base import Permission, Tool, ToolResult


class BashTool(Tool):
    """Execute bash commands in a shell."""

    name = "bash"
    description = """Execute a bash command in the system shell.

Use this for terminal operations like git, npm, docker, running tests, etc.
DO NOT use this for file operations (reading, writing, editing) - use the specialized tools instead.

## GUI Apps & Long-Running Processes
Use background=true for:
- GUI applications (pygame, tkinter, Qt, GTK, electron)
- Dev servers (npm start, python -m http.server)
- Any process that runs indefinitely

Example: bash(command="python game.py", background=true)

## Important
- Always quote file paths containing spaces with double quotes
- Use absolute paths when possible
- Commands will timeout after 120 seconds unless background=true
- Output is truncated if too long"""

    permission = Permission.EXECUTE

    def __init__(self, timeout: int = 120, max_output: int = 50000):
        self.timeout = timeout
        self.max_output = max_output

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (default: {self.timeout}, max: 300)",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory for command execution (default: current directory)",
                },
                "background": {
                    "type": "boolean",
                    "description": "Run process in background and return immediately. Use for GUI apps or long-running processes.",
                },
            },
            "required": ["command"],
        }

    async def execute(
        self,
        command: str,
        timeout: int | None = None,
        working_directory: str | None = None,
        background: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a bash command."""
        timeout = min(timeout or self.timeout, 300)
        cwd = working_directory or os.getcwd()
        
        # Forward full environment including DISPLAY for GUI apps
        env = {**os.environ}
        # Only set TERM to dumb for non-background processes
        if not background:
            env["TERM"] = "dumb"

        try:
            # Background mode: launch and return immediately
            if background:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    stdin=asyncio.subprocess.DEVNULL,
                    cwd=cwd,
                    env=env,
                    start_new_session=True,  # Detach from parent
                )
                return ToolResult(
                    success=True,
                    output=f"Background process started (PID: {process.pid})\nCommand: {command}\n\nProcess is running independently. Check manually or use `ps aux | grep {process.pid}` to verify.",
                )

            # Normal mode: wait for completion
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout} seconds. For long-running or GUI processes, use background=true.",
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Combine output
            output_parts = []
            if stdout_str:
                output_parts.append(stdout_str)
            if stderr_str:
                output_parts.append(f"[stderr]\n{stderr_str}")

            output = "\n".join(output_parts)

            # Truncate if needed
            if len(output) > self.max_output:
                output = output[: self.max_output] + f"\n... (truncated, {len(output)} chars total)"

            success = process.returncode == 0
            return ToolResult(
                success=success,
                output=output or "(no output)",
                error=None if success else f"Exit code: {process.returncode}",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to execute command: {e}",
            )
