## Purpose
Asset catalog containing all image/color sets that the app and extension share.

## Key Views/ViewModels/Services/Models
- `Contents.json` enumerates the color/icon styles and references the nested sets below.

## Data Flow & Interfaces
Build tool copies this catalog into the bundle so SwiftUI views can reference assets by name.

## Dependencies
Build system, SwiftUI (for `Image`/`Color`), and the asset sets themselves.

## Refactor Opportunities
Clean up unused variants if identifiers change in the design system.

Reviewed files: 1
