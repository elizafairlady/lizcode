"""Command-line interface for LizCode."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

from lizcode import __version__
from lizcode.config.settings import Settings, create_default_config
from lizcode.core.agent import Agent
from lizcode.core.session import SessionManager
from lizcode.core.state import ConversationState, Mode

console = Console()


class ToolDeclinedException(Exception):
    """Raised when user declines a tool and wants to provide input."""
    pass


async def ask_user_callback(question: str, options: list[str] | None, context: str | None) -> str:
    """Callback for asking user a question interactively.
    
    This is called by the ask_user tool to get input from the user.
    """
    console.print()
    
    # Show context if provided
    if context:
        console.print(f"[dim]{context}[/dim]")
        console.print()
    
    # Show question
    console.print(Panel(
        question,
        title="[cyan]Question[/cyan]",
        border_style="cyan",
    ))
    
    # Show options if provided
    if options:
        console.print("[dim]Options:[/dim]")
        for i, opt in enumerate(options, 1):
            console.print(f"  [cyan]{i}.[/cyan] {opt}")
        console.print()
    
    # Prompt for answer
    try:
        from prompt_toolkit import prompt as pt_prompt
        answer = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: pt_prompt("Your answer > ")
        )
        return answer.strip()
    except (EOFError, KeyboardInterrupt):
        return "(no response)"


async def generate_session_name(provider, message: str) -> str:
    """Generate a concise session name from user message using LLM."""
    prompt = f"""Generate a short 3-5 word name for this coding session/task:

{message[:500]}

Respond with ONLY the name, nothing else. Example: Fix Authentication Bug"""

    try:
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
        )
        name = response.get("content", "").strip()
        # Clean up any quotes or extra formatting
        name = name.strip('"\'`')
        return name[:50] if name else "New Session"
    except Exception:
        # Fallback to truncated message
        return message[:50] if message else "New Session"


class LizCodeCLI:
    """Main CLI application."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state = ConversationState()
        self.agent: Agent | None = None
        self.running = True
        self.session_mgr = SessionManager()
        self._first_message = True
        self._last_user_message = ""
        self._working_dir = Path.cwd()

        # Always start in plan mode
        self.state.set_mode(Mode.PLAN)

        # Initialize prompt session with history and multiline support
        history_file = Path.home() / ".lizcode" / "history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create model completer for tab completion
        from lizcode.tools.model_completer import ModelCompleter
        model_completer = ModelCompleter(settings)
        
        self._prompt_session = PromptSession(
            history=FileHistory(str(history_file)),
            multiline=False,  # Single line by default, use Meta+Enter for multiline
            enable_history_search=True,
            completer=model_completer,
        )
        self._model_completer = model_completer

    def _create_provider(self):
        """Create the model provider based on settings."""
        if self.settings.provider == "openrouter":
            if not self.settings.openrouter_api_key:
                console.print(
                    "[red]Error: OpenRouter API key not configured.[/red]\n"
                    "Set OPENROUTER_API_KEY environment variable or add to ~/.lizcode/config.yaml"
                )
                sys.exit(1)

            from lizcode.core.providers.openrouter import OpenRouterProvider

            return OpenRouterProvider(
                api_key=self.settings.openrouter_api_key,
                model=self.settings.openrouter_model,
                base_url=self.settings.openrouter_base_url,
            )
        else:
            from lizcode.core.providers.ollama import OllamaProvider

            return OllamaProvider(
                model=self.settings.ollama_model,
                host=self.settings.ollama_host,
            )

    def _get_language_for_file(self, file_path: str) -> str:
        """Detect language from file extension for syntax highlighting."""
        ext_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "jsx": "jsx",
            "tsx": "tsx",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "toml": "toml",
            "md": "markdown",
            "html": "html",
            "css": "css",
            "scss": "scss",
            "sh": "bash",
            "bash": "bash",
            "zsh": "bash",
            "sql": "sql",
            "rs": "rust",
            "go": "go",
            "rb": "ruby",
            "java": "java",
            "c": "c",
            "cpp": "cpp",
            "h": "c",
            "hpp": "cpp",
            "xml": "xml",
            "dockerfile": "dockerfile",
        }
        ext = Path(file_path).suffix.lstrip(".").lower()
        name = Path(file_path).name.lower()
        
        # Handle special filenames
        if name == "dockerfile":
            return "dockerfile"
        if name in ("makefile", "gnumakefile"):
            return "makefile"
        
        return ext_map.get(ext, ext or "text")

    def _approval_callback(self, tool_name: str, description: str, args: dict) -> bool:
        """Prompt user for tool approval.
        
        Raises ToolDeclinedException if user declines, allowing them to provide context.
        """
        console.print()

        if tool_name == "bash":
            cmd = args.get("command", "")
            panel_content = f"[bold]Command:[/bold]\n[yellow]{cmd}[/yellow]"
            console.print(Panel(
                panel_content,
                title=f"[yellow]Approve {tool_name}?[/yellow]",
                border_style="yellow",
            ))
        elif tool_name == "write_file":
            file_path = args.get("file_path", "")
            content = args.get("content", "")
            lang = self._get_language_for_file(file_path)
            
            console.print(Panel(
                f"[bold]File:[/bold] {file_path}",
                title=f"[yellow]Approve {tool_name}?[/yellow]",
                border_style="yellow",
            ))
            
            # Show syntax-highlighted content (truncated if too long)
            display_content = content
            if len(content) > 3000:
                display_content = content[:3000] + "\n\n... (truncated)"
            
            syntax = Syntax(display_content, lang, theme="monokai", line_numbers=True)
            console.print(syntax)
        elif tool_name == "edit_file":
            file_path = args.get("file_path", "")
            old_string = args.get("old_string", "")
            new_string = args.get("new_string", "")
            lang = self._get_language_for_file(file_path)
            
            console.print(Panel(
                f"[bold]File:[/bold] {file_path}",
                title=f"[yellow]Approve {tool_name}?[/yellow]",
                border_style="yellow",
            ))
            
            # Show old vs new with syntax highlighting
            console.print("[dim]--- Old ---[/dim]")
            old_display = old_string[:1500] + "\n..." if len(old_string) > 1500 else old_string
            console.print(Syntax(old_display, lang, theme="monokai"))
            
            console.print("[dim]=== New ===[/dim]")
            new_display = new_string[:1500] + "\n..." if len(new_string) > 1500 else new_string
            console.print(Syntax(new_display, lang, theme="monokai"))
        else:
            console.print(Panel(
                description,
                title=f"[yellow]Approve {tool_name}?[/yellow]",
                border_style="yellow",
            ))

        approved = Confirm.ask("Execute?", default=True)
        if not approved:
            # Raise exception to interrupt agent loop and let user provide context
            raise ToolDeclinedException(f"User declined {tool_name}")
        return True

    def _get_task_progress(self) -> str:
        """Get task progress string like [0/10]."""
        if not self.agent or not self.agent.task_list.tasks:
            return ""
        completed = sum(1 for t in self.agent.task_list.tasks if t.state.value == "completed")
        total = len(self.agent.task_list.tasks)
        return f"[{completed}/{total}]"

    def _get_prompt(self) -> str:
        """Get the input prompt based on current mode."""
        mode = self.state.mode
        if mode == Mode.PLAN:
            return "[bold blue]p[/bold blue] > "
        elif mode == Mode.ACT:
            progress = self._get_task_progress()
            if progress:
                return f"[bold green]a {progress}[/bold green] > "
            return "[bold green]a[/bold green] > "
        else:
            return "[bold yellow]sh[/bold yellow] > "

    def _print_welcome(self) -> None:
        """Print welcome message."""
        model = (
            self.settings.openrouter_model
            if self.settings.provider == "openrouter"
            else self.settings.ollama_model
        )

        console.print()
        console.print(Panel(
            f"[bold cyan]LizCode v{__version__}[/bold cyan]\n"
            f"AI pair programming assistant\n\n"
            f"[dim]Provider:[/dim] {self.settings.provider}\n"
            f"[dim]Model:[/dim] {model}\n\n"
            "[dim]Commands: /plan /act /sh /new /sessions /resume[/dim]\n"
            "[dim]Session: /checkpoints /rewind /tasks /clear /model /help /exit[/dim]",
            title="[bold]Welcome[/bold]",
            border_style="cyan",
        ))
        console.print()

    def _print_help(self) -> None:
        """Print help message."""
        help_text = """
[bold cyan]Mode Commands:[/bold cyan]
  /plan         Switch to Plan mode
  /act          Switch to Act mode
  /sh           Switch to Shell mode
  /aish         Switch to AI Shell mode (commands added to conversation)

[bold cyan]One-shot Commands:[/bold cyan]
  /plan <msg>   Run in Plan mode, return to current
  /act <msg>    Run in Act mode, return to current
  /sh <cmd>     Run shell command
  /aish <cmd>   Run command, add to AI conversation

[bold cyan]Session Commands:[/bold cyan]
  /new          Create new session
  /sessions     List sessions for this project
  /resume [id]  Resume a previous session

[bold cyan]Checkpoint Commands:[/bold cyan]
  /checkpoints  List checkpoints in session
  /rewind [N]   Rewind N checkpoints (default: 1)

[bold cyan]Other Commands:[/bold cyan]
  /tasks        Show task list
  /clear        Clear conversation
  /model        Show current model or switch with /model <provider/model>
  /help         This help
  /exit         Exit

[bold cyan]Modes:[/bold cyan]
  [blue]p[/blue]    Plan - read-only exploration
  [green]a[/green]    Act - full access with approval
  [yellow]sh[/yellow]   Shell - direct shell access
"""
        console.print(Panel(help_text.strip(), title="[bold]Help[/bold]", border_style="cyan"))

    def _print_tasks(self) -> None:
        """Print current task list."""
        if not self.agent or not self.agent.task_list.tasks:
            console.print("[dim]No tasks.[/dim]")
            return

        table = Table(title="Tasks", border_style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Status", style="bold")
        table.add_column("Task")

        for task in self.agent.task_list.tasks:
            if task.state.value == "pending":
                status = "[dim][ ][/dim]"
                text = task.content
            elif task.state.value == "in_progress":
                status = "[yellow][>][/yellow]"
                text = f"[yellow]{task.active_form}[/yellow]"
            else:
                status = "[green][x][/green]"
                text = f"[dim]{task.content}[/dim]"

            table.add_row(task.id, status, text)

        console.print(table)
        console.print(f"Progress: {self._get_task_progress()}")

    def _print_checkpoints(self) -> None:
        """Print checkpoint list."""
        session = self.session_mgr.current_session
        if not session or not session.checkpoints:
            console.print("[dim]No checkpoints yet.[/dim]")
            return

        table = Table(title="Checkpoints", border_style="cyan")
        table.add_column("#", style="dim")
        table.add_column("Message")
        table.add_column("Time", style="dim")

        for cp in session.checkpoints:
            # Format timestamp
            time_str = cp.timestamp.split("T")[1][:8] if "T" in cp.timestamp else cp.timestamp
            table.add_row(str(cp.number), cp.message, time_str)

        console.print(table)
        console.print(f"[dim]Session: {session.name} ({session.id[:8]})[/dim]")

    def _handle_rewind(self, count_str: str | None) -> None:
        """Handle /rewind command."""
        session = self.session_mgr.current_session
        if not session:
            console.print("[red]No active session.[/red]")
            return

        if not session.checkpoints:
            console.print("[red]No checkpoints to rewind to.[/red]")
            return

        # Parse the target checkpoint number
        target = len(session.checkpoints)
        if count_str:
            try:
                count = int(count_str)
                target = len(session.checkpoints) - count
            except ValueError:
                console.print("[red]Invalid count. Usage: /rewind [N][/red]")
                return

        if target < 1:
            target = 1

        success, message, conv_state = session.rewind_to(target)

        if success:
            console.print(f"[green]{message}[/green]")
            # Restore conversation state if available
            if conv_state:
                self.state.from_dict(conv_state.get("conversation", {}))
                if self.agent:
                    if "tasks" in conv_state:
                        from lizcode.core.tasks import TaskList
                        self.agent.task_list = TaskList.from_dict(conv_state["tasks"])
                    # Restore plan state
                    if "plan" in conv_state:
                        from lizcode.core.plan import Plan
                        self.agent.current_plan = Plan.from_dict(conv_state["plan"])
                        console.print(f"[dim]Restored plan: {self.agent.current_plan.title}[/dim]")
                    else:
                        self.agent.current_plan = None
        else:
            console.print(f"[red]{message}[/red]")

    def _print_sessions(self) -> None:
        """Print list of sessions for current project."""
        sessions = self.session_mgr.list_sessions(self._working_dir)
        if not sessions:
            console.print("[dim]No sessions for this project.[/dim]")
            return

        table = Table(title="Sessions", border_style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Checkpoints", style="dim")
        table.add_column("Updated", style="dim")

        current_id = self.session_mgr.current_session.id if self.session_mgr.current_session else None
        
        for s in sessions[:10]:  # Show last 10
            id_display = s.id[:8]
            if s.id == current_id:
                id_display = f"[green]{id_display}*[/green]"
            
            updated = s.updated_at.split("T")[0] if "T" in s.updated_at else s.updated_at
            table.add_row(id_display, s.name, str(len(s.checkpoints)), updated)

        console.print(table)

    def _handle_new_session(self) -> None:
        """Create a new session."""
        session = self.session_mgr.create_session(self._working_dir, "New Session")
        self.state.clear()
        if self.agent:
            self.agent.task_list.clear_all()
            self.agent.current_plan = None
        self._first_message = True
        console.print(f"[green]Created new session: {session.id[:8]}[/green]")

    def _handle_resume(self, session_id: str | None) -> None:
        """Resume a previous session."""
        if not session_id:
            # Resume most recent session
            session = self.session_mgr.get_most_recent_session(self._working_dir)
            if not session:
                console.print("[red]No sessions to resume.[/red]")
                return
        else:
            # Find session by ID prefix
            sessions = self.session_mgr.list_sessions(self._working_dir)
            session = None
            for s in sessions:
                if s.id.startswith(session_id):
                    session = s
                    break
            
            if not session:
                console.print(f"[red]Session not found: {session_id}[/red]")
                return

        # Load the session
        self.session_mgr.load_session(session.id)
        
        # Restore conversation state from last checkpoint
        if session.checkpoints:
            conv_state = session.load_checkpoint(len(session.checkpoints))
            if conv_state:
                self.state.from_dict(conv_state.get("conversation", {}))
                if self.agent:
                    if "tasks" in conv_state:
                        from lizcode.core.tasks import TaskList
                        self.agent.task_list = TaskList.from_dict(conv_state["tasks"])
                    # Restore plan state
                    if "plan" in conv_state:
                        from lizcode.core.plan import Plan
                        self.agent.current_plan = Plan.from_dict(conv_state["plan"])
                        console.print(f"[dim]Restored plan: {self.agent.current_plan.title}[/dim]")
        
        self._first_message = False
        console.print(f"[green]Resumed session: {session.name} ({session.id[:8]})[/green]")

    def _handle_model_switch(self, model_spec: str) -> tuple[bool, Any]:
        """Handle model switching: /model <provider/model>."""
        model_spec = model_spec.strip()
        
        if "/" in model_spec:
            # Full provider/model specification
            provider, model = model_spec.split("/", 1)
            provider = provider.lower()
            
            if provider not in ["openrouter", "ollama"]:
                console.print(f"[red]Unknown provider: {provider}. Use 'openrouter' or 'ollama'[/red]")
                return True, None
                
            # Update settings
            self.settings.provider = provider
            if provider == "openrouter":
                self.settings.openrouter_model = f"{provider}/{model}"
            else:  # ollama
                self.settings.ollama_model = model
                
        else:
            # Just model name, keep current provider
            if self.settings.provider == "openrouter":
                # For OpenRouter, assume the model_spec might be a full model id already
                if "/" in model_spec:
                    self.settings.openrouter_model = model_spec
                else:
                    # Try to find matching model with provider prefix
                    self.settings.openrouter_model = model_spec
            else:  # ollama
                self.settings.ollama_model = model_spec

        # Persist settings
        self._save_settings()
        
        # Show confirmation
        current_model = (
            self.settings.openrouter_model 
            if self.settings.provider == "openrouter" 
            else self.settings.ollama_model
        )
        console.print(f"[green]Switched to {self.settings.provider}: {current_model}[/green]")
        
        # Reset agent so it uses new provider/model on next interaction
        if self.agent:
            # We'll let the agent close naturally, just clear the reference
            # so a new one is created with the updated settings
            self.agent = None
            
        return True, None
        
    def _save_settings(self) -> None:
        """Save current settings to config file."""
        self.settings.save_to_yaml()

    def _handle_command(self, user_input: str) -> tuple[bool, Any]:
        """Handle a slash command. Returns (handled, one_shot_data)."""
        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else None

        # Exit commands
        if cmd in ("/exit", "/quit", "/q"):
            self.running = False
            console.print("[dim]Goodbye![/dim]")
            return True, None

        if cmd == "/help":
            self._print_help()
            return True, None

        if cmd == "/tasks":
            self._print_tasks()
            return True, None

        if cmd == "/checkpoints":
            self._print_checkpoints()
            return True, None

        if cmd == "/rewind":
            self._handle_rewind(rest)
            return True, None

        if cmd == "/new":
            self._handle_new_session()
            return True, None

        if cmd == "/sessions":
            self._print_sessions()
            return True, None

        if cmd == "/resume":
            self._handle_resume(rest)
            return True, None

        if cmd == "/clear":
            self.state.clear()
            if self.agent:
                self.agent.task_list.clear_all()
                self.agent.current_plan = None
            console.print("[dim]Conversation, tasks, and plan cleared.[/dim]")
            return True, None

        if cmd == "/model":
            if rest:
                # Switch model: /model <provider/model>
                return self._handle_model_switch(rest)
            else:
                # Show current model info
                console.print(f"[dim]Provider:[/dim] {self.settings.provider}")
                if self.settings.provider == "openrouter":
                    console.print(f"[dim]Model:[/dim] {self.settings.openrouter_model}")
                else:
                    console.print(f"[dim]Model:[/dim] {self.settings.ollama_model}")
                return True, None

        # Mode switching
        if cmd == "/plan":
            if rest:
                return False, ("plan", rest)
            self.state.set_mode(Mode.PLAN)
            if self.agent:
                self.agent.set_mode(Mode.PLAN)
            return True, None

        if cmd == "/act":
            # Check if we have a plan and auto-finalize if needed
            if self.agent and self.agent.current_plan:
                from lizcode.core.plan import PlanPhase
                plan = self.agent.current_plan
                if plan.phase != PlanPhase.READY_TO_EXECUTE:
                    console.print(f"[dim]Auto-finalizing plan (was '{plan.phase.value}')...[/dim]")
                    plan.phase = PlanPhase.READY_TO_EXECUTE
                    plan._persist()
                
                # Auto-populate tasks from plan
                if plan.steps and not self.agent.task_list.tasks:
                    self.agent.populate_tasks_from_plan()
                    console.print(f"[green]Loaded {len(self.agent.task_list.tasks)} tasks from plan.[/green]")
            
            if rest:
                # /act Go. or /act <message> - switch mode AND send message
                self.state.set_mode(Mode.ACT)
                if self.agent:
                    self.agent.set_mode(Mode.ACT)
                return False, ("act", rest)
            
            self.state.set_mode(Mode.ACT)
            if self.agent:
                self.agent.set_mode(Mode.ACT)
            return True, None

        if cmd in ("/sh", "/shell", ":"):
            if rest:
                self._run_bash_command(rest)
                return True, None
            self.state.set_mode(Mode.BASH)
            return True, None

        if cmd == "/aish":
            if rest:
                # One-shot: run command and inject into conversation
                self._run_aish_command(rest)
                return True, None
            # Switch to AISH mode
            self.state.set_mode(Mode.AISH)
            console.print("[cyan]Switched to AI Shell mode. Commands will be added to conversation.[/cyan]")
            return True, None

        return False, None

    def _run_bash_command(self, command: str) -> None:
        """Run a bash command in the user's shell."""
        try:
            subprocess.run(
                command,
                shell=True,
                cwd=os.getcwd(),
            )
        except KeyboardInterrupt:
            console.print("\n[dim]^C[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _run_aish_command(self, command: str) -> None:
        """Run a bash command and inject result into conversation as a tool call/result.
        
        This allows the user to run verification commands and have the AI see the results.
        """
        from uuid import uuid4
        from lizcode.core.state import ToolCall, ToolResult as StateToolResult
        
        console.print(f"[dim]$ {command}[/dim]")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=120,
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            output = output.strip() or "(no output)"
            success = result.returncode == 0
            
        except subprocess.TimeoutExpired:
            output = f"Command timed out after 120 seconds"
            success = False
        except KeyboardInterrupt:
            output = "Command interrupted"
            success = False
            console.print("\n[dim]^C[/dim]")
        except Exception as e:
            output = f"Error: {e}"
            success = False
        
        # Display output
        console.print(output)
        
        # Create synthetic tool call and result
        tool_call_id = str(uuid4())[:8]
        tool_call = ToolCall(
            id=tool_call_id,
            name="bash",
            arguments={"command": command},
        )
        
        # Add to conversation state
        self.state.add_assistant_message("", tool_calls=[tool_call])
        self.state.add_tool_result(StateToolResult(
            tool_call_id=tool_call_id,
            name="bash",
            result=output,
            success=success,
        ))
        
        style = "green" if success else "red"
        console.print(f"[{style}]Added to conversation as bash tool result[/{style}]")

    def _get_conversation_state(self) -> dict[str, Any]:
        """Get current conversation state for checkpointing."""
        state = {
            "conversation": self.state.to_dict(),
            "mode": self.state.mode.value,
        }
        if self.agent:
            state["tasks"] = self.agent.task_list.to_dict()
            # Include plan state so it survives rewind
            if self.agent.current_plan:
                state["plan"] = self.agent.current_plan.to_dict()
        return state

    async def _process_ai_response(self, user_input: str, temp_mode: Mode | None = None) -> None:
        """Process user input through the AI agent."""
        self._last_user_message = user_input

        if not self.agent:
            provider = self._create_provider()
            
            # Initialize session on first real message with LLM-generated name
            if self._first_message:
                console.print("[dim]Generating session name...[/dim]")
                name = await generate_session_name(provider, user_input)
                session = self.session_mgr.create_session(self._working_dir, name)
                console.print(f"[dim]Session: {name} ({session.id[:8]})[/dim]")
                self._first_message = False

            self.agent = Agent(
                provider=provider,
                state=self.state,
                approval_callback=self._approval_callback,
                question_callback=ask_user_callback,
                working_directory=Path.cwd(),
            )

        # Temporarily switch mode if needed
        original_mode = None
        if temp_mode and temp_mode != self.state.mode:
            original_mode = self.state.mode
            self.state.set_mode(temp_mode)
            self.agent.set_mode(temp_mode)

        console.print()

        try:
            full_response = []
            _ever_streamed = False  # Track if we ever streamed anything

            async for chunk in self.agent.chat(user_input):
                chunk_type = chunk.get("type")

                if chunk_type == "content":
                    text = chunk.get("text", "")
                    # Stream text immediately for better UX
                    if text.strip():
                        _ever_streamed = True
                        console.print(text, end="", markup=False)
                    else:
                        # Track non-streamed content for fallback
                        full_response.append(text)

                elif chunk_type == "tool_call":
                    # Ensure we're on a new line if streaming was active
                    if _ever_streamed:
                        console.print()  # Add newline after streamed content
                    
                    tool = chunk.get("tool")
                    args = chunk.get("args", {})
                    
                    # Format plan tools cleanly
                    if tool == "create_plan":
                        title = args.get("title", "")
                        objective = args.get("objective", "")
                        console.print(f"[blue]📋 Creating plan:[/blue] {title}")
                        if objective:
                            console.print(f"[dim]   Objective: {objective}[/dim]")
                    elif tool == "update_plan":
                        action = args.get("action", "")
                        content = args.get("content", "")
                        action_icons = {
                            "add_context": "📝",
                            "add_step": "➕",
                            "add_file": "📄",
                            "add_verification": "✓",
                            "set_approach": "🎯",
                            "add_risk": "⚠️",
                        }
                        icon = action_icons.get(action, "•")
                        # Truncate content if too long
                        display_content = content[:80] + "..." if len(content) > 80 else content
                        console.print(f"[blue]{icon} {action}:[/blue] {display_content}")
                    elif tool == "finalize_plan":
                        summary = args.get("summary", "")
                        ready = args.get("ready_to_implement", True)
                        status = "✅ Ready" if ready else "📝 Needs review"
                        console.print(f"[blue]📋 Finalizing plan:[/blue] {status}")
                    else:
                        console.print(f"[dim]Using tool: {tool}[/dim]")

                elif chunk_type == "tool_result":
                    tool = chunk.get("tool")
                    result = chunk.get("result", "")
                    success = chunk.get("success", True)

                    # Skip displaying certain tools - their results are internal
                    if tool in ("todo_write", "read_file", "list_files", "glob", "grep", 
                                "create_plan", "update_plan", "finalize_plan", "ask_user") and success:
                        continue

                    # Special handling for attempt_completion - simple one-line output
                    if tool == "attempt_completion" and success:
                        # Extract first paragraph as summary
                        lines = result.split("\n")
                        summary = ""
                        for line in lines:
                            line = line.strip()
                            if line and not line.startswith("#") and not line.startswith("```"):
                                summary = line[:100] + ("..." if len(line) > 100 else "")
                                break
                        console.print()
                        console.print(f"[bold green]✅ Task complete:[/bold green] {summary}")
                        continue

                    # For task tool, show just the summary, not full reasoning
                    if tool == "task" and success:
                        # Extract just the agent type and brief result
                        lines = result.split("\n")
                        summary_lines = []
                        for line in lines[:3]:  # First 3 lines have the summary
                            if line.strip():
                                summary_lines.append(line)
                        if summary_lines:
                            console.print(Panel(
                                "\n".join(summary_lines),
                                title="[green]task[/green]",
                                border_style="green",
                            ))
                        continue

                    display_result = result
                    if len(display_result) > 1000:
                        display_result = display_result[:1000] + "\n[dim]... (truncated)[/dim]"

                    style = "green" if success else "red"
                    console.print(Panel(
                        display_result,
                        title=f"[{style}]{tool}[/{style}]",
                        border_style=style,
                    ))

                elif chunk_type == "error":
                    console.print(f"[red]Error: {chunk.get('message')}[/red]")

                elif chunk_type == "mode_change":
                    new_mode = chunk.get("mode")
                    if new_mode == "plan":
                        self.state.set_mode(Mode.PLAN)
                        if self.agent:
                            self.agent.set_mode(Mode.PLAN)
                        console.print("[blue]Entered Plan mode[/blue]")
                    elif new_mode == "act":
                        self.state.set_mode(Mode.ACT)
                        if self.agent:
                            self.agent.set_mode(Mode.ACT)
                        console.print("[green]Switched to Act mode[/green]")

                elif chunk_type == "task_update":
                    tasks = chunk.get("tasks", "")
                    console.print(f"[dim]{tasks}[/dim]")

                elif chunk_type == "iteration_limit":
                    count = chunk.get("count", 0)
                    console.print()
                    console.print(f"[yellow]⚠ Reached {count} iterations in this response.[/yellow]")
                    continue_exec = Confirm.ask("Continue execution?", default=True)
                    if not continue_exec:
                        console.print("[dim]Stopping execution. You can continue with another message.[/dim]")
                        break

            # Only print final response if we have non-streamed content
            if full_response and not _ever_streamed:
                response_text = "".join(full_response)
                try:
                    md = Markdown(response_text)
                    console.print(md)
                except Exception:
                    console.print(response_text)
            elif _ever_streamed:
                # Newline after streamed content
                console.print()

            # Create checkpoint after successful interaction
            session = self.session_mgr.current_session
            if session:
                checkpoint = session.create_checkpoint(
                    message=user_input[:50] + ("..." if len(user_input) > 50 else ""),
                    conversation_state=self._get_conversation_state(),
                )
                console.print(f"[dim]Checkpoint {checkpoint.number}[/dim]")

        except ToolDeclinedException as e:
            # User declined a tool - return control so they can provide context
            console.print(f"\n[yellow]Declined:[/yellow] {e}")
            console.print("[dim]You can now provide context or instructions before continuing.[/dim]")
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

        # Restore original mode if we temporarily switched
        if original_mode:
            self.state.set_mode(original_mode)
            self.agent.set_mode(original_mode)

        console.print()

    def _get_plain_prompt(self) -> str:
        """Get plain text prompt for prompt_toolkit (no rich markup)."""
        mode = self.state.mode
        if mode == Mode.PLAN:
            return "p > "
        elif mode == Mode.ACT:
            progress = self._get_task_progress()
            if progress:
                return f"a {progress} > "
            return "a > "
        elif mode == Mode.AISH:
            return "aish > "
        else:
            return "sh > "

    async def run(self) -> None:
        """Main run loop."""
        self._print_welcome()

        while self.running:
            try:
                prompt = self._get_plain_prompt()

                try:
                    user_input = await self._prompt_session.prompt_async(prompt)
                except EOFError:
                    self.running = False
                    break
                except KeyboardInterrupt:
                    console.print("\n[dim]Use /exit to quit[/dim]")
                    continue

                user_input = user_input.strip()

                if not user_input:
                    continue

                # Check for slash commands
                if user_input.startswith("/") or user_input == ":":
                    handled, one_shot = self._handle_command(user_input)
                    if handled:
                        continue
                    if one_shot:
                        mode_name, message = one_shot
                        temp_mode = Mode.PLAN if mode_name == "plan" else Mode.ACT
                        await self._process_ai_response(message, temp_mode=temp_mode)
                        continue

                # Handle based on mode
                if self.state.mode == Mode.BASH:
                    self._run_bash_command(user_input)
                elif self.state.mode == Mode.AISH:
                    self._run_aish_command(user_input)
                else:
                    await self._process_ai_response(user_input)

            except KeyboardInterrupt:
                console.print("\n[dim]Use /exit to quit[/dim]")
                continue

        # Cleanup
        if self.agent:
            await self.agent.close()
        if hasattr(self, '_model_completer'):
            await self._model_completer.close()


@click.command()
@click.option(
    "--provider", "-p",
    type=click.Choice(["openrouter", "ollama"]),
    help="Model provider to use",
)
@click.option(
    "--model", "-m",
    help="Model to use",
)
@click.version_option(version=__version__)
def main(
    provider: str | None,
    model: str | None,
) -> None:
    """LizCode - AI pair programming CLI with Plan, Act, and Shell modes."""
    create_default_config()
    settings = Settings.load_from_yaml()

    if provider:
        settings.provider = provider
    if model:
        if settings.provider == "openrouter":
            settings.openrouter_model = model
        else:
            settings.ollama_model = model

    cli = LizCodeCLI(settings)
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
