## Purpose
Swift Package Manager lockfile for the workspace.

## Key Views/ViewModels/Services/Models
- `Package.resolved` pins third-party dependencies the iOS app uses.

## Data Flow & Interfaces
When running `uv sync` or `xcodebuild`, the package manager consults this to resolve exact versions.

## Dependencies
Swift Package Manager and any packages referenced in the PM manifest.

## Refactor Opportunities
Regenerate via `uv sync` whenever package versions change; avoid manual edits.

Reviewed files: 1
