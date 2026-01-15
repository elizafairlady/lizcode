"""Tests for file tools: read_file, write_file, edit_file, glob, grep, list_files."""

from __future__ import annotations

import os
import pytest
from pathlib import Path


class TestReadFileTool:
    """Tests for read_file tool."""

    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path, monkeypatch) -> None:
        """Should read file contents."""
        from lizcode.tools.read_file import ReadFileTool
        
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        tool = ReadFileTool()
        result = await tool.execute(file_path=str(test_file))
        
        assert result.success
        assert "Hello, World!" in result.output

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tmp_path, monkeypatch) -> None:
        """Should fail gracefully for missing file."""
        from lizcode.tools.read_file import ReadFileTool
        
        monkeypatch.chdir(tmp_path)
        
        tool = ReadFileTool()
        result = await tool.execute(file_path=str(tmp_path / "nonexistent.txt"))
        
        assert not result.success

    @pytest.mark.asyncio
    async def test_read_relative_path(self, tmp_path, monkeypatch) -> None:
        """Should read file from relative path."""
        from lizcode.tools.read_file import ReadFileTool
        
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "relative.txt"
        test_file.write_text("Relative content")
        
        tool = ReadFileTool()
        result = await tool.execute(file_path="relative.txt")
        
        assert result.success
        assert "Relative content" in result.output


class TestWriteFileTool:
    """Tests for write_file tool."""

    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_path, monkeypatch) -> None:
        """Should create new file."""
        from lizcode.tools.write_file import WriteFileTool
        
        monkeypatch.chdir(tmp_path)
        
        tool = WriteFileTool()
        new_file = tmp_path / "new.txt"
        
        result = await tool.execute(file_path=str(new_file), content="New content")
        
        assert result.success
        assert new_file.exists()
        assert new_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_overwrite_file(self, tmp_path, monkeypatch) -> None:
        """Should overwrite existing file."""
        from lizcode.tools.write_file import WriteFileTool
        
        monkeypatch.chdir(tmp_path)
        existing = tmp_path / "existing.txt"
        existing.write_text("Old content")
        
        tool = WriteFileTool()
        result = await tool.execute(file_path=str(existing), content="New content")
        
        assert result.success
        assert existing.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_create_parent_dirs(self, tmp_path, monkeypatch) -> None:
        """Should create parent directories."""
        from lizcode.tools.write_file import WriteFileTool
        
        monkeypatch.chdir(tmp_path)
        
        tool = WriteFileTool()
        deep_file = tmp_path / "a" / "b" / "c" / "file.txt"
        
        result = await tool.execute(file_path=str(deep_file), content="Deep")
        
        assert result.success
        assert deep_file.exists()
        assert deep_file.read_text() == "Deep"


class TestEditFileTool:
    """Tests for edit_file tool."""

    @pytest.mark.asyncio
    async def test_edit_with_search_replace(self, tmp_path, monkeypatch) -> None:
        """Should replace content using search/replace."""
        from lizcode.tools.edit_file import EditFileTool
        
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    return 'old'\n")
        
        tool = EditFileTool()
        result = await tool.execute(
            file_path=str(test_file),
            old_string="return 'old'",
            new_string="return 'new'",
        )
        
        assert result.success
        assert "return 'new'" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_edit_search_not_found(self, tmp_path, monkeypatch) -> None:
        """Should fail if search string not found."""
        from lizcode.tools.edit_file import EditFileTool
        
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    pass\n")
        
        tool = EditFileTool()
        result = await tool.execute(
            file_path=str(test_file),
            old_string="nonexistent text",
            new_string="replacement",
        )
        
        assert not result.success


class TestGlobTool:
    """Tests for glob tool."""

    @pytest.mark.asyncio
    async def test_glob_pattern(self, tmp_path, monkeypatch) -> None:
        """Should find files matching glob pattern."""
        from lizcode.tools.glob import GlobTool
        
        monkeypatch.chdir(tmp_path)
        
        # Create test files
        (tmp_path / "a.py").write_text("# a")
        (tmp_path / "b.py").write_text("# b")
        (tmp_path / "c.txt").write_text("c")
        
        tool = GlobTool()
        result = await tool.execute(pattern="*.py")
        
        assert result.success
        assert "a.py" in result.output
        assert "b.py" in result.output
        assert "c.txt" not in result.output

    @pytest.mark.asyncio
    async def test_glob_recursive(self, tmp_path, monkeypatch) -> None:
        """Should find files recursively."""
        from lizcode.tools.glob import GlobTool
        
        monkeypatch.chdir(tmp_path)
        
        # Create nested files
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (tmp_path / "top.py").write_text("# top")
        (subdir / "nested.py").write_text("# nested")
        
        tool = GlobTool()
        result = await tool.execute(pattern="**/*.py")
        
        assert result.success
        assert "top.py" in result.output
        assert "nested.py" in result.output


class TestGrepTool:
    """Tests for grep tool."""

    @pytest.mark.asyncio
    async def test_grep_pattern(self, tmp_path, monkeypatch) -> None:
        """Should find lines matching pattern."""
        from lizcode.tools.grep import GrepTool
        
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    pass\ndef bar():\n    pass\n")
        
        tool = GrepTool()
        result = await tool.execute(pattern="def", path=str(tmp_path))
        
        assert result.success
        assert "def foo" in result.output
        assert "def bar" in result.output

    @pytest.mark.asyncio
    async def test_grep_regex(self, tmp_path, monkeypatch) -> None:
        """Should support regex patterns."""
        from lizcode.tools.grep import GrepTool
        
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "test.py"
        test_file.write_text("foo123\nbar456\nbaz\n")
        
        tool = GrepTool()
        result = await tool.execute(pattern=r"\w+\d+", path=str(tmp_path))
        
        assert result.success
        assert "foo123" in result.output or "bar456" in result.output


class TestListFilesTool:
    """Tests for list_files tool."""

    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path, monkeypatch) -> None:
        """Should list directory contents."""
        from lizcode.tools.list_files import ListFilesTool
        
        monkeypatch.chdir(tmp_path)
        
        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.txt").write_text("2")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        
        tool = ListFilesTool()
        result = await tool.execute(path=str(tmp_path))
        
        assert result.success
        assert "file1.txt" in result.output
        assert "file2.txt" in result.output
        assert "subdir" in result.output

    @pytest.mark.asyncio
    async def test_list_cwd_default(self, tmp_path, monkeypatch) -> None:
        """Should list current directory by default."""
        from lizcode.tools.list_files import ListFilesTool
        
        monkeypatch.chdir(tmp_path)
        (tmp_path / "cwd_file.txt").write_text("test")
        
        tool = ListFilesTool()
        result = await tool.execute(path=".")
        
        assert result.success
        assert "cwd_file.txt" in result.output
