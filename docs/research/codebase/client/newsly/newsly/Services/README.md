## Purpose
Business logic tier: networking, notifications, voice streaming, onboarding, and feature-specific helpers.

## Key Views/ViewModels/Services/Models
- `APIClient.swift` centralizes HTTP requests and handles response decoding.
- `ContentService.swift`, `DiscoveryService.swift`, and `LongFormStatsService.swift` orchestrate content fetching and analytics.
- `AuthenticationService.swift`, `AppSettings.swift`, and `KeychainManager.swift` guard sensitive state.
- `LiveVoiceAudioCaptureEngine.swift`, `VoiceWebSocketClient.swift`, and `RealtimeTranscriptionService.swift` support live voice experiences.
- `ToastService.swift`, `UnreadCountService.swift`, and `ProcessingCountService.swift` manage app status indicators.

## Data Flow & Interfaces
ViewModels request operations from these services, services use `APIClient`/`OpenAIService.swift` to hit backend endpoints, and results bubble back via Combine/async to update models/stores.

## Dependencies
URLSession/Foundation for networking, `SwiftUI` for alert binding, `AVFoundation`/`Speech` for audio helpers, and the shared `SharedContainer` credential helpers.

## Refactor Opportunities
The service directory is large—consider grouping voice/audio services under a dedicated module and splitting the general-purpose `ContentService` into smaller pieces to make responsibilities more explicit.

Reviewed files: 29
