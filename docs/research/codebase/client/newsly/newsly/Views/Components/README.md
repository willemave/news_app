## Purpose
Reusable SwiftUI components (cards, banners, filters, markdown renderers, etc.) used throughout the app.

## Key Views/ViewModels/Services/Models
- `ArticleCardView.swift`, `ContentCard.swift`, and `LongFormCard.swift` render summarized content/longform stories.
- `ChatStatusBanner.swift`, `ChatMarkdownTheme.swift`, and `ChatLoadingView.swift` support chat UI polish.
- `DiscoverySuggestionCard.swift`, `FilterBar.swift`, `FilterSheet.swift`, and `DownloadMoreMenu.swift` drive discovery state control.
- `StructuredSummaryView.swift`, `InterleavedSummaryView.swift`, and `EditorialNarrativeSummaryView.swift` render AI-generated summaries.
- `LiveVoiceActiveView.swift`, `LiveVoiceIdleView.swift`, and `LiveVoiceAmbientBackground.swift` compose the live voice scene.

## Data Flow & Interfaces
Higher-level views feed these components with viewmodel data, and the components emit actions/events (e.g., tapping a card) back to their parents.

## Dependencies
SwiftUI, `Models` for metadata, and `Services` for image caching and markdown rendering.

## Refactor Opportunities
Bundle related components into submodules (e.g., a `Card` module) and document the input/output contracts for widely reused views.

Reviewed files: 40
