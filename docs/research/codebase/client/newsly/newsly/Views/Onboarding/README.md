## Purpose
Onboarding screens composing the immersive first-time experience (animated reveal, how it works, mic prompts).

## Key Views/ViewModels/Services/Models
- `OnboardingFlowView.swift` coordinates `AncientScrollRevealView.swift`, `WhatItDoes` (assuming `HowItWorksModal`), and `OnboardingMicButton.swift`.
- `RevealPhysicsScene.swift` backs the scroll animation.
- `HowItWorksModal.swift` explains the app, while `AncientScrollRevealProgressTests.swift` (in tests) might target the reveal animation.

## Data Flow & Interfaces
Onboarding views send decisions to `OnboardingViewModel`, which triggers `OnboardingStateStore` updates and eventually unlocks main content. 

## Dependencies
SwiftUI animation APIs, CA for physics, and `ViewModels` for state.

## Refactor Opportunities
Consider breaking onboarding into smaller composable pieces so the reveal animation can be reused elsewhere.

Reviewed files: 5
