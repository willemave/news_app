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
    private var lastKnownUser: User?

    init() {
#if DEBUG
        authState = .authenticated(Self.developmentUser())
#else
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
#endif
    }

    /// Check if user is already authenticated on app launch
    func checkAuthStatus() {
        authState = .loading

#if DEBUG
        authState = .authenticated(Self.developmentUser())
#else

        let hasRefreshToken = KeychainManager.shared.getToken(key: .refreshToken) != nil
        let hasAccessToken = KeychainManager.shared.getToken(key: .accessToken) != nil

        // No tokens at all -> user must sign in
        guard hasRefreshToken || hasAccessToken else {
            authState = .unauthenticated
            return
        }

        Task {
            do {
                let user = try await authService.getCurrentUser()
                lastKnownUser = user
                authState = .authenticated(user)
            } catch let authError as AuthError {
                await handleAuthFailure(authError, hasRefreshToken: hasRefreshToken)
            } catch {
                authState = .unauthenticated
            }
        }
#endif
    }

    /// Sign in with Apple
    func signInWithApple() {
        authState = .loading
        errorMessage = nil

        Task {
            do {
                let user = try await authService.signInWithApple()
                lastKnownUser = user
                authState = .authenticated(user)
            } catch {
                errorMessage = error.localizedDescription
                authState = .unauthenticated
            }
        }
    }

    /// Logout current user
    func logout() {
#if DEBUG
        authState = .authenticated(Self.developmentUser())
#else
        authService.logout()
        lastKnownUser = nil
        authState = .unauthenticated
#endif
    }

#if DEBUG
    private static func developmentUser() -> User {
        User(
            id: -1,
            appleId: "dev",
            email: "dev@local",
            fullName: "Development User",
            isAdmin: true,
            isActive: true,
            createdAt: Date(timeIntervalSince1970: 0),
            updatedAt: Date(timeIntervalSince1970: 0)
        )
    }
#endif

    // MARK: - Private

    private func handleAuthFailure(_ error: AuthError, hasRefreshToken: Bool) async {
        switch error {
        case .notAuthenticated:
            guard hasRefreshToken else {
                authService.logout()
                authState = .unauthenticated
                return
            }
            await refreshAndLoadUser()
        case .refreshTokenExpired, .noRefreshToken:
            authService.logout()
            authState = .unauthenticated
        case .networkError(let underlying):
            errorMessage = underlying.localizedDescription
            // Keep tokens; allow retry without forcing logout
            if let user = lastKnownUser {
                authState = .authenticated(user)
            } else {
                authState = .loading
            }
        case .serverError(_, let message):
            errorMessage = message
            if let user = lastKnownUser {
                authState = .authenticated(user)
            } else {
                authState = .loading
            }
        default:
            authService.logout()
            authState = .unauthenticated
        }
    }

    private func refreshAndLoadUser() async {
        do {
            _ = try await authService.refreshAccessToken()
            let user = try await authService.getCurrentUser()
            lastKnownUser = user
            authState = .authenticated(user)
            print("✅ User authenticated successfully after refresh")
        } catch let authError as AuthError {
            switch authError {
            case .refreshTokenExpired, .noRefreshToken:
                authService.logout()
                authState = .unauthenticated
            case .networkError(let underlying):
                errorMessage = underlying.localizedDescription
                if let user = lastKnownUser {
                    authState = .authenticated(user)
                } else {
                    authState = .loading
                }
            case .serverError(_, let message):
                errorMessage = message
                if let user = lastKnownUser {
                    authState = .authenticated(user)
                } else {
                    authState = .loading
                }
            default:
                authService.logout()
                authState = .unauthenticated
            }
        } catch {
            authService.logout()
            authState = .unauthenticated
        }
    }
}
