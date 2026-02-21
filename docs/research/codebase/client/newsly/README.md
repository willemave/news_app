## Purpose
Top-level iOS workspace wrapper that coordinates the Share Extension target, the main newsly target, and ancillary configuration/scripts for the SwiftUI app.

## Key Views/ViewModels/Services/Models
- `newsly.xcodeproj` wires the SwiftUI app and extension targets under one workspace.
- `Secrets.xcconfig.template` documents the env variables (Database URL, JWT secret, admin password) that the native app expects.
- `sync-secrets.sh` and `uv` commands keep the generated xcconfigs in sync with the repo-wide secrets expectations.
- `.gitignore` keeps derived data plus Xcode cache cruft out of commits.

## Data Flow & Interfaces
CI/dev runs `sync-secrets.sh` before `uv sync`/`xcodebuild` so the xcconfigs referenced by the target contain the latest secrets and entitlements.

## Dependencies
Depends on the Xcode toolchain/`xcodebuild`, the `uv` dependency manager, and the system Swift compiler; no runtime code lives here.

## Refactor Opportunities
Consider templating secrets per target and deleting the stale `Info.plist.backup` that is no longer referenced by any target.

Reviewed files: 4
