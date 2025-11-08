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

        // Validate token with backend and get current user
        Task {
            do {
                let user = try await authService.getCurrentUser()
                authState = .authenticated(user)
            } catch {
                // Token validation failed - try to refresh before logging out
                print("⚠️ Access token validation failed, attempting refresh...")

                // Check if we have a refresh token
                guard KeychainManager.shared.getToken(key: .refreshToken) != nil else {
                    print("❌ No refresh token available - logging out")
                    authState = .unauthenticated
                    return
                }

                do {
                    // Try to refresh the access token
                    _ = try await authService.refreshAccessToken()
                    print("✅ Token refresh successful, fetching user info...")

                    // Try to get user again with new token
                    let user = try await authService.getCurrentUser()
                    authState = .authenticated(user)
                    print("✅ User authenticated successfully after refresh")
                } catch {
                    // Refresh also failed - user needs to sign in again
                    print("❌ Token refresh failed: \(error.localizedDescription)")
                    authState = .unauthenticated
                }
            }
        }
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
