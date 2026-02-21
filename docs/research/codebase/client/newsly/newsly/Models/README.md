## Purpose
Structs/enums that model the domain (content metadata, chat sessions, transcription routes, and onboarding state).

## Key Views/ViewModels/Services/Models
- `ContentDetail.swift`, `ContentSummary.swift`, and `StructuredSummary.swift` capture article/podcast payloads from the backend.
- `ChatMessage.swift`, `ChatSessionDetail.swift`, and `ChatSessionSummary.swift` represent interactive chat state.
- `ArticleMetadata.swift`, `NewsMetadata.swift`, and `PodcastMetadata.swift` describe source-specific metadata.
- `Onboarding.swift`, `DetectedFeed.swift`, and `LiveVoiceRoute.swift` capture configuration choices and routing hints.
- `User.swift` plus `SubmissionStatusItem.swift` drive UI personalization and status badges.

## Data Flow & Interfaces
`APIClient`/`ContentService` decode JSON into these models, view models mutate/observe them, and services like `LiveVoice` or `Chat` read them to drive UI updates.

## Dependencies
Foundation/`Codable`/`AnyCodable`, `SwiftData` (if applicable), and `SwiftUI` previews.

## Refactor Opportunities
Some metadata structs share fields—after confirming backend contracts, introduce protocols or shared base structs to eliminate duplication and tighten typing.

Reviewed files: 29
