## Purpose
Shared schemes that Xcode uses to run/build the app.

## Key Views/ViewModels/Services/Models
- `newsly.xcscheme` is the primary execution/test scheme for the app target.

## Data Flow & Interfaces
Xcode uses the scheme to know which target to build when hitting Run/Test.

## Dependencies
Scheme file references `newsly.xcodeproj` targets and configs only.

## Refactor Opportunities
Regenerate from Xcode if the scheme drifts out of sync.

Reviewed files: 1
