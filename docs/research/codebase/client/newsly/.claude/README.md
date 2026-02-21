## Purpose
Claude-local configuration that limits the shell commands the assistant can execute against this repo.

## Key Views/ViewModels/Services/Models
- `settings.local.json` enumerates the allow-list of shell commands for Claude-driven automation.

## Data Flow & Interfaces
The Claude agent reads this file before issuing any `Bash(...)` commands so only approved operations run.

## Dependencies
Only the Claude assistant (external) and json parsing built into the CLI touch this file.

## Refactor Opportunities
Add a README or comments documenting when to refresh the allowed command list if new scripts are introduced.

Reviewed files: 1
