## Purpose
Shared UI building blocks across multiple screens (buttons, badges, sections).

## Key Views/ViewModels/Services/Models
- `AddButton.swift`, `GlassCard.swift`, `SearchBar.swift`, and `SectionDivider.swift` are reused wrappers.
- `StatusChip.swift`, `SourceRow.swift`, and `AppBadge.swift` provide consistent avatar/text combos.
- `EmptyStateView.swift` and `WatercolorBackground.swift` handle fallback/visual decoration.

## Data Flow & Interfaces
Each shared component receives data from parent views and returns interactions via closures.

## Dependencies
SwiftUI/`DesignTokens.swift` for colors and typography.

## Refactor Opportunities
Ensure spacing/magic numbers live in `DesignTokens` so these components don’t diverge from the design language.

Reviewed files: 12
