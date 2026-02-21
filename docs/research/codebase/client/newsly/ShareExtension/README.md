## Purpose
Share extension target that lets users push URLs/links directly into newsly without launching the full app.

## Key Views/ViewModels/Services/Models
- `ShareViewController.swift` orchestrates the native share UI and hands off data to the shared container.
- `Info.plist` configures the extension point (`NSExtension` entry) and supported item types.
- `ShareExtension.entitlements` enables app groups/keychain access required to communicate with the container app.

## Data Flow & Interfaces
iOS instantiates `ShareViewController` via the storyboard, the controller writes the URL or snippet into the shared container, and the host app picks it up when re-launched.

## Dependencies
Relies on UIKit for the extension UI and on `SharedContainer`/Keychain helpers defined in the main target via app group entitlements.

## Refactor Opportunities
Move the storyboard-less UI into SwiftUI so it shares view logic with the main landing flow and add explicit error handling before passing data to the host.

Reviewed files: 3
