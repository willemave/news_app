//
//  AuthenticatedRootView.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import SwiftUI

private enum AuthenticatedPresentationState {
    case deciding
    case onboarding
    case tutorial
    case content
}

struct AuthenticatedRootView: View {
    @EnvironmentObject var authViewModel: AuthenticationViewModel
    let user: User

    @State private var presentationState: AuthenticatedPresentationState = .deciding

    private let onboardingStateStore = OnboardingStateStore.shared
    private let onboardingService = OnboardingService.shared

    var body: some View {
        Group {
            switch presentationState {
            case .deciding:
                LoadingView()
            case .onboarding:
                OnboardingFlowView(user: user) { response in
                    onboardingStateStore.clearPending(userId: user.id)
                    if !response.hasCompletedNewUserTutorial {
                        presentationState = .tutorial
                    } else {
                        presentationState = .content
                    }
                }
            case .tutorial:
                HowItWorksModal {
                    Task { await completeTutorial() }
                }
            case .content:
                ContentView()
                    .environmentObject(authViewModel)
                    .withToast()
                    .task {
                        await LocalNotificationService.shared.requestAuthorization()
                    }
            }
        }
        .onAppear {
            updatePresentation()
        }
        .onChange(of: authViewModel.lastSignInWasNewUser) { _, _ in
            updatePresentation()
        }
        .onChange(of: user.id) { _, _ in
            updatePresentation()
        }
        .onChange(of: user.hasCompletedNewUserTutorial) { _, _ in
            updatePresentation()
        }
    }

    private func updatePresentation() {
        let needsOnboarding = authViewModel.lastSignInWasNewUser || onboardingStateStore.needsOnboarding(userId: user.id)
        if needsOnboarding {
            presentationState = .onboarding
            authViewModel.lastSignInWasNewUser = false
            return
        }

        if !user.hasCompletedNewUserTutorial {
            presentationState = .tutorial
            return
        }

        presentationState = .content
    }

    private func completeTutorial() async {
        presentationState = .content
        do {
            let response = try await onboardingService.markTutorialComplete()
            if response.hasCompletedNewUserTutorial {
                authViewModel.updateUser(updatedUserTutorialFlag(true))
            }
        } catch {
            ToastService.shared.showError("Failed to save tutorial status: \(error.localizedDescription)")
        }
    }

    private func updatedUserTutorialFlag(_ completed: Bool) -> User {
        User(
            id: user.id,
            appleId: user.appleId,
            email: user.email,
            fullName: user.fullName,
            twitterUsername: user.twitterUsername,
            hasXBookmarkSync: user.hasXBookmarkSync,
            isAdmin: user.isAdmin,
            isActive: user.isActive,
            hasCompletedNewUserTutorial: completed,
            hasCompletedLiveVoiceOnboarding: user.hasCompletedLiveVoiceOnboarding,
            createdAt: user.createdAt,
            updatedAt: user.updatedAt
        )
    }
}
