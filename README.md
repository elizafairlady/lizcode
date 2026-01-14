# LizCode

AI pair programming CLI with Plan, Act, and Bash modes - inspired by Claude Code and Gemini CLI.

## Features

### Three Operating Modes

- **Plan Mode**: Read-only exploration and planning
  - LizCode explores the codebase using read-only tools
  - Launches explore/plan subagents in parallel
  - Creates a structured plan saved to `.lizcode/plan.md`
  - No file modifications allowed

- **Act Mode**: Full access with approval prompts
  - LizCode can modify files and run commands
  - User must approve write/edit/execute operations
  - TaskList tracks progress on multi-step work
  - Can switch to Plan mode for complex tasks

- **Bash Mode**: Direct shell access
  - User has direct access to the shell
  - LizCode is paused
  - Type `/plan` or `/act` to return

### Task Management (TodoWrite)

Like Claude Code, LizCode proactively creates task lists for complex work:

```
[x] Read existing authentication code
[>] Creating auth middleware
[ ] Add login endpoint
[ ] Add JWT token handling
[ ] Run tests
```

Tasks have states: `pending`, `in_progress`, `completed`
- Only one task can be `in_progress` at a time
- Tasks are marked complete immediately after finishing

### Subagent System

True subprocess-based subagents for parallel exploration:

- **explore**: Codebase exploration (read-only)
- **plan**: Design implementation approaches
- **test_runner**: Run and report test results
- **build_validator**: Validate builds succeed
- **code_reviewer**: Review code for issues

Subagents can run:
- In parallel (async workers) for quick operations
- In background (subprocess) for long-running tasks

### Model Providers

- **OpenRouter**: Access to Claude, GPT-4, Llama, and many other models
- **Ollama**: Run local models like Llama, CodeLlama, Deepseek

## Installation

```bash
cd lizcode
uv venv
uv pip install -e .

# Or with pip
pip install -e .
```

## Configuration

Create `~/.lizcode/config.yaml` (auto-created on first run):

```yaml
# Model provider: "openrouter" or "ollama"
provider: openrouter

# OpenRouter settings
openrouter_api_key: your-api-key-here
openrouter_model: anthropic/claude-sonnet-4

# Ollama settings (for local models)
ollama_host: http://localhost:11434
ollama_model: llama3.2

# Default mode: "plan" or "act"
default_mode: act
```

Or use environment variables:
```bash
export OPENROUTER_API_KEY=your-api-key
```

## Usage

```bash
# Start LizCode
.venv/bin/lizcode

# Start with specific provider
lizcode --provider ollama --model codellama

# Start in plan mode
lizcode --mode plan
```

### Commands

| Command | Description |
|---------|-------------|
| `/plan` | Switch to Plan mode (read-only) |
| `/act` | Switch to Act mode (full access) |
| `/sh` | Switch to Shell mode |
| `/plan <msg>` | One-shot: run in Plan mode, return to current |
| `/act <msg>` | One-shot: run in Act mode, return to current |
| `/sh <cmd>` | Run shell command without switching modes |
| `/checkpoints` | List checkpoints in current session |
| `/rewind [N]` | Rewind N checkpoints (default: 1) |
| `/merge` | Merge session branch to original |
| `/tasks` | Show current task list |
| `/clear` | Clear conversation |
| `/model` | Show current model |
| `/help` | Show help |
| `/exit` | Exit LizCode |

### Example Session

```
[act] > Add user authentication to this Flask app

Creating task list...

┌─────────────────────────────────────────────┐
│ Tasks                                       │
├─────────────────────────────────────────────┤
│ [ ] Explore existing codebase               │
│ [ ] Create auth middleware                  │
│ [ ] Add login/logout endpoints              │
│ [ ] Add JWT token handling                  │
│ [ ] Test authentication flow                │
└─────────────────────────────────────────────┘

Entering Plan mode to explore the codebase...

[plan] > (explores files, launches subagents)

Found Flask app structure. Here's my plan:

## Plan Summary
1. Add Flask-JWT-Extended for token handling
2. Create auth blueprint with login/logout routes
3. Add middleware to protect routes
4. Write tests

Ready to implement. Approve to switch to Act mode.

[plan] > /act

[act] > (implements changes with approval prompts)

┌──────────────────────────────────────────────┐
│ Approve write_file?                          │
│                                              │
│ File: src/auth.py                            │
│ Creating authentication blueprint...         │
└──────────────────────────────────────────────┘
Execute? [Y/n]: y
```

## Architecture

```
lizcode/
├── cli.py              # Main CLI entry point
├── core/
│   ├── agent.py        # Main agent orchestration
│   ├── prompts.py      # System prompts for modes
│   ├── state.py        # Conversation state
│   ├── tasks.py        # TaskList management
│   ├── plan.py         # Plan file system
│   ├── subagent.py     # Subagent spawning (async + subprocess)
│   └── providers/      # LLM providers (OpenRouter, Ollama)
├── tools/
│   ├── base.py         # Tool base class with permissions
│   ├── bash.py         # Bash command execution
│   ├── read_file.py    # File reading
│   ├── write_file.py   # File writing
│   ├── edit_file.py    # File editing
│   ├── glob.py         # File search by pattern
│   ├── grep.py         # Content search
│   ├── list_files.py   # Directory listing
│   ├── todo_write.py   # Task list management
│   ├── task.py         # Subagent spawning
│   └── mode.py         # Plan mode tools
└── config/
    └── settings.py     # Configuration management
```

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Test imports
python -c "from lizcode.core.agent import Agent; print('OK')"
```

## License

MIT
