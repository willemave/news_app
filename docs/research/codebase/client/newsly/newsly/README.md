## Purpose
Primary SwiftUI app target that defines the landing/auth flow, info plist, and entitlements.

## Key Views/ViewModels/Services/Models
- `newslyApp.swift` is the @main entry point, toggling between `LandingView` and `AuthenticatedRootView` via `AuthenticationViewModel`.
- `ContentView.swift` appears to host the root navigation container referenced by SwiftUI previews.
- `Info.plist` and `newsly.entitlements` describe permissions, app identifiers, and capabilities.
- `Info.plist.backup` is an older copy that should probably be trimmed once confirmed unused.

## Data Flow & Interfaces
`newslyApp` configures the shared keychain group on init, observes auth state, and injects environment objects into `LandingView`/`AuthenticatedRootView` to start service chains.

## Dependencies
Depends heavily on SwiftUI, Combine/ObservableObjects (`AuthenticationViewModel`), and `KeychainManager`/`SharedContainer` for secure storage.

## Refactor Opportunities
Drop the stale backup, scope `ContentView` to a clearer responsibility, and ensure the env injection path is documented for future viewmodels.

Reviewed files: 5
