## Purpose
Settings screen to inspect/change user preferences.

## Key Views/ViewModels/Services/Models
- `SettingsView.swift` lists rows for theme, notifications, and linking to support.

## Data Flow & Interfaces
Hooks into `ViewModels`/`Services` (e.g., `KeychainManager`, `AppSettings`) to read/write toggles.

## Dependencies
SwiftUI form components and `Services` for persistence.

## Refactor Opportunities
Add dedicated SettingsViewModel to avoid passing services directly into the view.

Reviewed files: 1
