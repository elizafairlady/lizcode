"""Tests specifically for GUI process launching."""

from __future__ import annotations

import asyncio
import os
import re
import signal
import tempfile
from pathlib import Path

import pytest

from lizcode.tools.bash import BashTool


class TestGUIApps:
    """Test that GUI apps can actually launch."""

    @pytest.fixture
    def simple_pygame_script(self, temp_dir: Path) -> Path:
        """Create a simple pygame script that writes to a file to prove it ran."""
        script = temp_dir / "test_pygame.py"
        marker = temp_dir / "pygame_started.marker"
        
        script.write_text(f'''#!/usr/bin/env python3
"""Simple pygame test that creates a marker file when it starts."""
import sys
from pathlib import Path

# Write marker immediately to prove script started
Path("{marker}").write_text("started")

try:
    import pygame
    pygame.init()
    
    # Try to create a display (this is where it might fail)
    try:
        screen = pygame.display.set_mode((100, 100))
        Path("{marker}").write_text("display_created")
    except pygame.error as e:
        Path("{marker}").write_text(f"display_failed: {{e}}")
        sys.exit(0)  # Exit cleanly if no display
    
    # Run for a short time
    pygame.display.set_caption("Test Window")
    Path("{marker}").write_text("running")
    
    start = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start < 2000:  # 2 seconds
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                break
        pygame.display.flip()
        pygame.time.wait(100)
    
    Path("{marker}").write_text("completed")
    pygame.quit()
except ImportError:
    Path("{marker}").write_text("no_pygame")
except Exception as e:
    Path("{marker}").write_text(f"error: {{e}}")
''')
        return script, marker

    @pytest.mark.asyncio
    async def test_pygame_script_can_start(self, simple_pygame_script, bash_tool: BashTool) -> None:
        """Test if a pygame script can even start in background mode.
        
        This test verifies:
        1. The process starts
        2. The script actually begins executing
        3. We can detect if the display was created
        """
        script, marker = simple_pygame_script
        
        # Clean up marker
        if marker.exists():
            marker.unlink()
        
        result = await bash_tool.execute(
            command=f"python {script}",
            background=True,
        )
        assert result.success, f"Failed to start: {result.error}"
        
        # Extract PID
        match = re.search(r'PID: (\d+)', result.output)
        assert match, f"No PID in output: {result.output}"
        pid = int(match.group(1))
        
        # Wait for script to initialize
        await asyncio.sleep(1.5)
        
        # Check if marker file was created
        assert marker.exists(), (
            f"Script did not start - no marker file created.\n"
            f"PID was {pid}\n"
            f"Check if process is alive: ps -p {pid}"
        )
        
        status = marker.read_text()
        print(f"Pygame test status: {status}")
        
        # Acceptable outcomes:
        # - "running" or "completed" = success (pygame worked)
        # - "no_pygame" = pygame not installed (skip)
        # - "display_failed" = no display available (OK for headless CI)
        # - "started" = script started but pygame didn't init
        
        if status == "no_pygame":
            pytest.skip("pygame not installed")
        elif status.startswith("display_failed"):
            # This is OK - means the script ran, just no display available
            pass
        elif status.startswith("error"):
            pytest.fail(f"Script error: {status}")
        else:
            assert status in ("started", "running", "completed", "display_created"), (
                f"Unexpected status: {status}"
            )
        
        # Cleanup
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    @pytest.fixture
    def simple_gui_script(self, temp_dir: Path) -> Path:
        """Create a simple script that opens a window without pygame."""
        script = temp_dir / "test_gui.py"
        marker = temp_dir / "gui_started.marker"
        
        # Try tkinter as it's in stdlib
        script.write_text(f'''#!/usr/bin/env python3
"""Test if we can open any GUI window."""
import sys
from pathlib import Path

Path("{marker}").write_text("started")

try:
    import tkinter as tk
    Path("{marker}").write_text("tk_imported")
    
    root = tk.Tk()
    Path("{marker}").write_text("tk_root_created")
    root.title("Test")
    root.geometry("100x100")
    
    # Run briefly
    root.after(1500, root.destroy)
    Path("{marker}").write_text("running")
    root.mainloop()
    Path("{marker}").write_text("completed")
except Exception as e:
    Path("{marker}").write_text(f"error: {{e}}")
''')
        return script, marker

    @pytest.mark.asyncio
    async def test_tkinter_can_start_background(self, simple_gui_script, bash_tool: BashTool) -> None:
        """Test if tkinter can start in background mode."""
        script, marker = simple_gui_script
        
        if marker.exists():
            marker.unlink()
        
        result = await bash_tool.execute(
            command=f"python {script}",
            background=True,
        )
        assert result.success
        
        match = re.search(r'PID: (\d+)', result.output)
        assert match
        pid = int(match.group(1))
        
        await asyncio.sleep(1.5)
        
        assert marker.exists(), f"Script did not start (PID {pid})"
        
        status = marker.read_text()
        print(f"Tkinter test status: {status}")
        
        # Any of these mean the script actually ran
        assert status not in ("", "started"), (
            f"Script started but stopped too early at: {status}"
        )
        
        # Cleanup
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


class TestEnvironmentForGUI:
    """Test that environment is properly set up for GUI apps."""

    @pytest.mark.asyncio
    async def test_display_is_passed(self, bash_tool: BashTool) -> None:
        """Test that DISPLAY environment variable is available."""
        result = await bash_tool.execute(
            command="echo DISPLAY=$DISPLAY",
            background=False,
        )
        assert result.success
        
        # Check if DISPLAY is set in current env
        if display := os.environ.get("DISPLAY"):
            assert display in result.output, (
                f"DISPLAY={display} not passed to subprocess.\n"
                f"Output: {result.output}"
            )

    @pytest.mark.asyncio
    async def test_term_not_dumb_for_background(self, bash_tool: BashTool, temp_dir: Path) -> None:
        """Test that TERM is not set to 'dumb' for background processes."""
        script = temp_dir / "check_term.py"
        marker = temp_dir / "term.marker"
        
        script.write_text(f'''
import os
from pathlib import Path
Path("{marker}").write_text(os.environ.get("TERM", "not_set"))
import time
time.sleep(2)
''')
        
        result = await bash_tool.execute(
            command=f"python {script}",
            background=True,
        )
        
        await asyncio.sleep(0.5)
        
        if marker.exists():
            term = marker.read_text()
            # For background processes, TERM should NOT be 'dumb'
            # because that can cause issues with some GUI/ncurses apps
            assert term != "dumb", "TERM should not be 'dumb' for background processes"
