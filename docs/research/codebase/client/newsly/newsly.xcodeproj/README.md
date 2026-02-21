## Purpose
Xcode project manifest (`project.pbxproj`) that enumerates targets, sources, and build settings for the app and extension.

## Key Views/ViewModels/Services/Models
- `project.pbxproj` describes the SwiftUI app, share extension, and their build phases/configurations.

## Data Flow & Interfaces
Xcode/`xcodebuild` reads this file to know how to compile/link each target from the source tree.

## Dependencies
Xcode manages this file; it references targets, configs, and asset catalogs but has no runtime dependencies.

## Refactor Opportunities
Keep the pbxproj diff-free by minimizing manual edits; consider moving shared build settings into xcconfigs for clarity.

Reviewed files: 1
