## Purpose
Shared workspace metadata that normalizes editor/IDE preferences between collaborators.

## Key Views/ViewModels/Services/Models
- `WorkspaceSettings.xcsettings` toggles Save Workspace Settings and ensures schemes stay shared.

## Data Flow & Interfaces
Xcode reads this on workspace load to respect user preferences like tab behavior.

## Dependencies
Xcode only.

## Refactor Opportunities
Leave untouched unless workspace behavior needs to change.

Reviewed files: 1
