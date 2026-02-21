## Purpose
Singleton-like stores for session-related UI state that crosses view/viewmodel boundaries.

## Key Views/ViewModels/Services/Models
- `ChatScrollStateStore.swift` remembers scroll positions for SES chat sessions.
- `OnboardingStateStore.swift` keeps track of progress through the intro flows.
- `ReadingStateStore.swift` surfaces read-later state across tabs.
- `SharedContainer.swift` wires the app group, keychain, and caches.

## Data Flow & Interfaces
ViewModels write to these stores and independent SwiftUI views observe them to stay in sync with cross-cutting concerns.

## Dependencies
SwiftUI/Combine for observation and `SharedContainer` for credential sharing.

## Refactor Opportunities
Document ownership of each store and ensure they expose clear APIs so they can be mocked or replaced in tests.

Reviewed files: 4
