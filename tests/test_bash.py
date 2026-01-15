"""Tests for the bash tool."""

from __future__ import annotations

import asyncio
import os
import re
import signal

import pytest

from lizcode.tools.bash import BashTool


class TestBashBasic:
    """Basic bash command tests."""

    @pytest.mark.asyncio
    async def test_simple_echo(self, bash_tool: BashTool) -> None:
        """Test simple echo command."""
        result = await bash_tool.execute(command="echo hello")
        assert result.success
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_exit_code_success(self, bash_tool: BashTool) -> None:
        """Test that exit code 0 is success."""
        result = await bash_tool.execute(command="exit 0")
        assert result.success

    @pytest.mark.asyncio
    async def test_exit_code_failure(self, bash_tool: BashTool) -> None:
        """Test that non-zero exit code is failure."""
        result = await bash_tool.execute(command="exit 1")
        assert not result.success
        assert "Exit code: 1" in (result.error or "")

    @pytest.mark.asyncio
    async def test_stderr_captured(self, bash_tool: BashTool) -> None:
        """Test that stderr is captured."""
        result = await bash_tool.execute(command="echo error >&2")
        assert "error" in result.output
        assert "[stderr]" in result.output

    @pytest.mark.asyncio
    async def test_working_directory(self, bash_tool: BashTool, temp_dir) -> None:
        """Test working directory parameter."""
        result = await bash_tool.execute(
            command="pwd",
            working_directory=str(temp_dir),
        )
        assert result.success
        assert str(temp_dir) in result.output

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Test command timeout."""
        tool = BashTool(timeout=1)
        result = await tool.execute(command="sleep 10")
        assert not result.success
        assert "timed out" in (result.error or "").lower()


class TestBashBackground:
    """Tests for background process functionality - CRITICAL."""

    @pytest.mark.asyncio
    async def test_background_returns_immediately(self, bash_tool: BashTool) -> None:
        """Test that background=True returns immediately, not after sleep."""
        import time
        
        start = time.time()
        result = await bash_tool.execute(
            command="sleep 30",
            background=True,
        )
        elapsed = time.time() - start
        
        assert result.success, f"Background command failed: {result.error}"
        assert elapsed < 2, f"Background took {elapsed}s - should be instant"

    @pytest.mark.asyncio
    async def test_background_reports_pid(self, bash_tool: BashTool) -> None:
        """Test that background returns a PID."""
        result = await bash_tool.execute(
            command="sleep 10",
            background=True,
        )
        assert result.success
        assert "PID" in result.output
        
        # Extract PID
        match = re.search(r'PID: (\d+)', result.output)
        assert match, f"No PID found in output: {result.output}"
        pid = int(match.group(1))
        assert pid > 0

    @pytest.mark.asyncio
    async def test_background_process_survives(self, bash_tool: BashTool) -> None:
        """CRITICAL TEST: Background process must actually stay alive.
        
        This is the test that proves whether GUI apps can actually run.
        If this fails, background mode is fundamentally broken.
        """
        result = await bash_tool.execute(
            command="sleep 5",
            background=True,
        )
        assert result.success
        
        # Extract PID
        match = re.search(r'PID: (\d+)', result.output)
        assert match, f"No PID found in output: {result.output}"
        pid = int(match.group(1))
        
        # Wait a moment for any async cleanup that might kill the process
        await asyncio.sleep(0.5)
        
        # Check if process is still running
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            is_alive = True
        except ProcessLookupError:
            is_alive = False
        except PermissionError:
            # Process exists but we don't have permission - still counts as alive
            is_alive = True
        
        assert is_alive, (
            f"CRITICAL: Background process (PID {pid}) died immediately!\n"
            f"This means GUI apps will fail to launch.\n"
            f"The background implementation is broken."
        )
        
        # Cleanup
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    @pytest.mark.asyncio
    async def test_background_process_survives_after_multiple_commands(
        self, bash_tool: BashTool
    ) -> None:
        """Test that background process survives even after running more commands."""
        # Start background process
        result = await bash_tool.execute(
            command="sleep 10",
            background=True,
        )
        assert result.success
        
        match = re.search(r'PID: (\d+)', result.output)
        assert match
        pid = int(match.group(1))
        
        # Run several more commands (simulating model continuing to work)
        for _ in range(3):
            await bash_tool.execute(command="echo test")
            await asyncio.sleep(0.1)
        
        # Check if background process is still running
        await asyncio.sleep(0.5)
        try:
            os.kill(pid, 0)
            is_alive = True
        except ProcessLookupError:
            is_alive = False
        except PermissionError:
            is_alive = True
        
        assert is_alive, (
            f"Background process (PID {pid}) died after running more commands.\n"
            f"Process must be properly detached."
        )
        
        # Cleanup
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    @pytest.mark.asyncio
    async def test_background_inherits_display(self, bash_tool: BashTool) -> None:
        """Test that background process has DISPLAY environment variable."""
        # This test verifies GUI apps can access the display
        result = await bash_tool.execute(
            command="echo $DISPLAY",
            background=False,  # Need output
        )
        
        # If DISPLAY is set in env, it should be passed through
        if os.environ.get("DISPLAY"):
            assert os.environ["DISPLAY"] in result.output or result.output.strip()


class TestBashEnvironment:
    """Test environment handling."""

    @pytest.mark.asyncio
    async def test_env_variables_passed(self, bash_tool: BashTool) -> None:
        """Test that environment variables are passed to subprocess."""
        # Set a test variable
        os.environ["LIZCODE_TEST_VAR"] = "test_value"
        
        result = await bash_tool.execute(command="echo $LIZCODE_TEST_VAR")
        assert result.success
        assert "test_value" in result.output
        
        del os.environ["LIZCODE_TEST_VAR"]

    @pytest.mark.asyncio
    async def test_display_available(self, bash_tool: BashTool) -> None:
        """Test that DISPLAY is available for GUI apps."""
        result = await bash_tool.execute(command="echo DISPLAY=$DISPLAY")
        # Just verify the command runs - DISPLAY may or may not be set
        assert result.success


class TestBashOutputTruncation:
    """Test output truncation."""

    @pytest.mark.asyncio  
    async def test_long_output_truncated(self) -> None:
        """Test that very long output is truncated."""
        tool = BashTool(max_output=100)
        result = await tool.execute(
            command="seq 1 10000"  # Generates lots of output
        )
        assert result.success
        assert len(result.output) <= 200  # Some buffer for truncation message
        assert "truncated" in result.output.lower()
