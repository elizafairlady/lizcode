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

Important:
- Always quote file paths containing spaces with double quotes
- Use absolute paths when possible
- Commands will timeout after the specified duration
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
            },
            "required": ["command"],
        }

    async def execute(
        self,
        command: str,
        timeout: int | None = None,
        working_directory: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a bash command."""
        timeout = min(timeout or self.timeout, 300)
        cwd = working_directory or os.getcwd()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env={**os.environ, "TERM": "dumb"},
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
                    error=f"Command timed out after {timeout} seconds",
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
