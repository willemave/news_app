## Purpose
Views dedicated to displaying and managing feed/podcast sources.

## Key Views/ViewModels/Services/Models
- `FeedSourcesView.swift`, `PodcastSourcesView.swift`, and `SourceDetailSheet.swift` expose discovery of RSS/Atom feeds.

## Data Flow & Interfaces
`ViewModels` drive the lists, tapping a source triggers `DiscoveryService` work via `Services`. 

## Dependencies
SwiftUI `List`/`Sheet` plus `Models/DetectedFeed`. 

## Refactor Opportunities
Share a single source list view and parameterize the filtering to decrease duplication.

Reviewed files: 3
