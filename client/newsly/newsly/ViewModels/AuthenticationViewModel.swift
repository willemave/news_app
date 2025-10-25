//
//  AuthenticationViewModel.swift
//  newsly
//
//  Created by Assistant on 10/25/25.
//

import Foundation
import SwiftUI

/// Authentication state
enum AuthState: Equatable {
    case loading
    case unauthenticated
    case authenticated(User)
}

/// View model managing authentication state
@MainActor
final class AuthenticationViewModel: ObservableObject {
    @Published var authState: AuthState = .loading
    @Published var errorMessage: String?

    private let authService = AuthenticationService.shared

    init() {
        checkAuthStatus()

        // Listen for authentication required notifications
        NotificationCenter.default.addObserver(
            forName: .authenticationRequired,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                self?.logout()
            }
        }
    }

    /// Check if user is already authenticated on app launch
    func checkAuthStatus() {
        authState = .loading

        // Check if we have a stored access token
        guard KeychainManager.shared.getToken(key: .accessToken) != nil else {
            authState = .unauthenticated
            return
        }

        // TODO: Validate token with backend or decode locally
        // For MVP, we'll just check if token exists
        // In production, call /auth/me to get current user

        // For now, if token exists, consider authenticated
        // This is temporary - we need to implement proper token validation
        authState = .unauthenticated
    }

    /// Sign in with Apple
    func signInWithApple() {
        authState = .loading
        errorMessage = nil

        Task {
            do {
                let user = try await authService.signInWithApple()
                authState = .authenticated(user)
            } catch {
                errorMessage = error.localizedDescription
                authState = .unauthenticated
            }
        }
    }

    /// Logout current user
    func logout() {
        authService.logout()
        authState = .unauthenticated
    }
}
