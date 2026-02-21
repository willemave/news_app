## Purpose
Library tab subset focusing on saved content.

## Key Views/ViewModels/Services/Models
- `FavoritesView.swift` shows bookmarked content pulled from `ReadStatusRepository`.

## Data Flow & Interfaces
`FavoritesView` pulls models via `ViewModels` and allows quick actions like re-reading or sharing.

## Dependencies
Library uses `ViewModels`, `Repositories`, and `Components` to render favorites list.

## Refactor Opportunities
Add pagination or section grouping helpers if the favorites list grows large.

Reviewed files: 1
