## Purpose
Unit tests guarding UI-specific behaviors.

## Key Views/ViewModels/Services/Models
- `AncientScrollRevealProgressTests.swift` verifies the onboarding animation state.
- `ShareURLRoutingTests.swift` confirms share-extension/deep-link routing logic.

## Data Flow & Interfaces
These tests instantiate viewmodels/views and simulate user flows to assert state transitions.

## Dependencies
XCTest and SwiftUI preview/test helpers.

## Refactor Opportunities
Expand coverage beyond the two tests to include viewmodels and services, especially networking helpers.

Reviewed files: 2
