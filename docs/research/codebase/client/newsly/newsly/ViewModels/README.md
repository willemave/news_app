## Purpose
ObservableObject classes that expose state/intentions for every screen in the SwiftUI app.

## Key Views/ViewModels/Services/Models
- `AuthenticationViewModel.swift` governs the login/user state machine seen in `newslyApp.swift`.
- `ContentListViewModel.swift`, `LongContentListViewModel.swift`, and `ShortNewsListViewModel.swift` prepare feed data for list views.
- `ChatSessionViewModel.swift`, `ChatSessionsViewModel.swift`, and `LiveVoiceViewModel.swift` mediate session-based experiences.
- `DiscoveryViewModel.swift` and `TabCoordinatorViewModel.swift` orchestrate navigation between discovery, library, and search.
- `OnboardingViewModel.swift`, `SubmissionStatusViewModel.swift`, and `LiveVoiceViewModel.swift` keep specialized flows separate.

## Data Flow & Interfaces
ViewModels call services/repositories, map models to UI-friendly state, and expose `@Published` properties consumed by views (and sometimes passed back to services via callbacks).

## Dependencies
Combine/SwiftUI observation, `Services` for backend interactions, and `Shared` stores for cross-screen state.

## Refactor Opportunities
Audit shared logic (e.g., pagination, toast handling) and extract helper objects so viewmodels stay focused on screen state rather than navigation glue.

Reviewed files: 20
