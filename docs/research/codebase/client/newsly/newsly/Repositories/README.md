## Purpose
Persistence helpers for storing read status and content snapshots.

## Key Views/ViewModels/Services/Models
- `ContentRepository.swift` caches article/podcast metadata locally.
- `ReadStatusRepository.swift` tracks which content has been read/bookmarked.

## Data Flow & Interfaces
ViewModels call these repositories when network responses arrive to persist data, and the repositories feed cached models back to views.

## Dependencies
Likely relies on FileManager/CoreData (as implemented inside) and the shared `AppSettings` service for configuration.

## Refactor Opportunities
Add protocols/interfaces so mocks can be injected into tests or new persistence layers (e.g., Core Data + SQL) without rewiring view models.

Reviewed files: 2
