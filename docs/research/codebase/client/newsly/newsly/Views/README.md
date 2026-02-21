## Purpose
Screen-level SwiftUI views covering authentication, landing, library, discovery, and chat.

## Key Views/ViewModels/Services/Models
- `LandingView.swift`/`AuthenticatedRootView.swift` are the gating screens controlled by auth state.
- `ContentListView.swift`, `SubmissionDetailView.swift`, and `SubmissionsView.swift` render the curated content feeds.
- `SearchView.swift`, `KnowledgeView.swift`, and `Library/FavoritesView.swift` present auxiliary flows.
- `ChatSessionView.swift`, `ProcessingStatsView.swift`, and `KnowledgeLiveView.swift` show the interactive/live experiences.
- `DebugMenuView.swift` and `MoreView.swift` expose tools/settings.

## Data Flow & Interfaces
Views subscribe to their corresponding viewmodels, send user interactions back through bindings/actions, and layer component subviews (from `Views/Components`).

## Dependencies
SwiftUI, `ViewModels`, `Components` and `Shared` stores for theming and state.

## Refactor Opportunities
Document the navigation graph linking `TabCoordinatorViewModel` to these screens, and consider segmenting `Views` into subfolders to mirror features.

Reviewed files: 18
