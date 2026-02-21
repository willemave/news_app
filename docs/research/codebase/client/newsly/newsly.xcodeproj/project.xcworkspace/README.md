## Purpose
Workspace container connecting the project to any additional Swift packages or tools.

## Key Views/ViewModels/Services/Models
- `contents.xcworkspacedata` points to `newsly.xcodeproj` inside the workspace.

## Data Flow & Interfaces
Xcode loads this workspace file first so it can show the project alongside Swift package dependencies.

## Dependencies
Only Xcode and workspace tools rely on this descriptor.

## Refactor Opportunities
No direct refactors; keep the entry lightweight to avoid workspace corruption.

Reviewed files: 1
