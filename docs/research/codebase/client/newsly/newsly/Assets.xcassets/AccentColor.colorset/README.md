## Purpose
Defines the system accent color for the app (used by SwiftUI).

## Key Views/ViewModels/Services/Models
- `Contents.json` names the accent color and can add dark/light variants.

## Data Flow & Interfaces
SwiftUI automatically uses this accent color when `accentColor` is not overridden.

## Dependencies
SwiftUI/Swift compiler only.

## Refactor Opportunities
Ensure the colorset matches the palette described in design tokens if the theme shifts.

Reviewed files: 1
