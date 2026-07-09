# AFDE Architecture v1

## Purpose

AFDE, AI Factory Development Environment, is the development workspace layer inside AI Factory OS.

It exists to move the project from manual patch application to AI-assisted development execution.

## Core Modules

```text
afde/
├── task_runner.py
├── workspace_manager.py
├── artifact_manager.py
├── git_manager.py
├── prompt_manager.py
├── provider_manager.py
└── cli.py
```

## Responsibilities

| Module | Responsibility |
|---|---|
| Task Runner | Creates and executes development tasks |
| Workspace Manager | Creates isolated sprint workspaces |
| Artifact Manager | Saves reports, plans, generated code, and manifests |
| Git Manager | Reads Git status and prepares safe commit commands |
| Prompt Manager | Stores and renders prompt templates |
| Provider Manager | Reports OpenAI/Gemini/Claude/Mock configuration |

## Safety Rule

AFDE-1 runs in local safe mode only.

It does not call paid APIs.
It does not push to GitHub automatically.
It does not delete project files.

## Next Stage

AFDE-2 will connect the AFDE runner to AI Factory OS CLI and then to the real worker runtime.
