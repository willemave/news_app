//
//  AuthenticatedRootView.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import SwiftUI

struct AuthenticatedRootView: View {
    @EnvironmentObject var authViewModel: AuthenticationViewModel
    let user: User

    @State private var showOnboarding = false
    @State private var showTutorial = false

    private let onboardingStateStore = OnboardingStateStore.shared
    private let onboardingService = OnboardingService.shared

    var body: some View {
        ContentView()
            .environmentObject(authViewModel)
            .withToast()
            .task {
                await LocalNotificationService.shared.requestAuthorization()
            }
            .fullScreenCover(isPresented: $showOnboarding) {
                OnboardingFlowView(user: user) { response in
                    onboardingStateStore.clearPending(userId: user.id)
                    showOnboarding = false
                    if !response.hasCompletedNewUserTutorial {
                        showTutorial = true
                    }
                }
            }
            .sheet(isPresented: $showTutorial) {
                HowItWorksModal {
                    Task { await completeTutorial() }
                }
            }
            .onAppear {
                updatePresentation()
            }
            .onChange(of: authViewModel.lastSignInWasNewUser) { _, _ in
                updatePresentation()
            }
            .onChange(of: user.hasCompletedNewUserTutorial) { _, _ in
                updatePresentation()
            }
    }

    private func updatePresentation() {
        let needsOnboarding = authViewModel.lastSignInWasNewUser || onboardingStateStore.needsOnboarding(userId: user.id)
        if needsOnboarding {
            showTutorial = false
            showOnboarding = true
            authViewModel.lastSignInWasNewUser = false
            return
        }

        if !user.hasCompletedNewUserTutorial {
            showTutorial = true
        }
    }

    private func completeTutorial() async {
        showTutorial = false
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
            isAdmin: user.isAdmin,
            isActive: user.isActive,
            hasCompletedNewUserTutorial: completed,
            createdAt: user.createdAt,
            updatedAt: user.updatedAt
        )
    }
}
