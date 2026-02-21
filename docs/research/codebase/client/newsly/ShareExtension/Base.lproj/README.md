## Purpose
Storyboard bundle that defines the Share Extension layout used during initial presentation.

## Key Views/ViewModels/Services/Models
- `MainInterface.storyboard` provides the lightweight container for `ShareViewController`.

## Data Flow & Interfaces
UIKit loads this storyboard when the extension is activated, then hands off to the view controller for logic.

## Dependencies
Depends on UIKit storyboard loading; no SwiftUI involvement yet.

## Refactor Opportunities
Replace this storyboard with a SwiftUI-backed scene to reuse the main app styles and simplify the controller stack.

Reviewed files: 1
