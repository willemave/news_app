//
//  AuthenticationService.swift
//  newsly
//
//  Created by Assistant on 10/25/25.
//

import Foundation
import AuthenticationServices
import CryptoKit

/// Authentication service handling Apple Sign In and token management
final class AuthenticationService: NSObject {
    static let shared = AuthenticationService()

    private override init() {
        super.init()
    }

    private var currentNonce: String?

    /// Sign in with Apple
    func signInWithApple() async throws -> User {
        let nonce = randomNonceString()
        currentNonce = nonce

        let appleIDProvider = ASAuthorizationAppleIDProvider()
        let request = appleIDProvider.createRequest()
        request.requestedScopes = [.fullName, .email]
        request.nonce = sha256(nonce)

        let authController = ASAuthorizationController(authorizationRequests: [request])

        return try await withCheckedThrowingContinuation { continuation in
            let delegate = AppleSignInDelegate(continuation: continuation, nonce: nonce)
            authController.delegate = delegate
            authController.presentationContextProvider = delegate
            authController.performRequests()

            // Keep delegate alive
            objc_setAssociatedObject(authController, "delegate", delegate, .OBJC_ASSOCIATION_RETAIN)
        }
    }

    /// Refresh access token using refresh token
    func refreshAccessToken() async throws -> String {
        guard let refreshToken = KeychainManager.shared.getToken(key: .refreshToken) else {
            throw AuthError.noRefreshToken
        }

        let url = URL(string: "\(AppSettings.shared.baseURL)/auth/refresh")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = RefreshTokenRequest(refreshToken: refreshToken)
        request.httpBody = try? JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw AuthError.refreshFailed
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let tokenResponse = try decoder.decode(AccessTokenResponse.self, from: data)

        // Save new access token
        KeychainManager.shared.saveToken(tokenResponse.accessToken, key: .accessToken)

        return tokenResponse.accessToken
    }

    /// Logout user (clear all tokens)
    func logout() {
        KeychainManager.shared.clearAll()
    }

    /// Get current user from backend
    func getCurrentUser() async throws -> User {
        guard let token = KeychainManager.shared.getToken(key: .accessToken) else {
            throw AuthError.notAuthenticated
        }

        let url = URL(string: "\(AppSettings.shared.baseURL)/auth/me")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AuthError.notAuthenticated
        }

        // If token is invalid/expired, throw auth error
        guard httpResponse.statusCode == 200 else {
            // Token is invalid - clear it
            KeychainManager.shared.clearAll()
            throw AuthError.notAuthenticated
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let user = try decoder.decode(User.self, from: data)
        return user
    }

    // MARK: - Private Helpers

    private func randomNonceString(length: Int = 32) -> String {
        precondition(length > 0)
        let charset: [Character] = Array("0123456789ABCDEFGHIJKLMNOPQRSTUVXYZabcdefghijklmnopqrstuvwxyz-._")
        var result = ""
        var remainingLength = length

        while remainingLength > 0 {
            let randoms: [UInt8] = (0..<16).map { _ in
                var random: UInt8 = 0
                let errorCode = SecRandomCopyBytes(kSecRandomDefault, 1, &random)
                if errorCode != errSecSuccess {
                    fatalError("Unable to generate nonce. SecRandomCopyBytes failed with OSStatus \(errorCode)")
                }
                return random
            }

            randoms.forEach { random in
                if remainingLength == 0 {
                    return
                }

                if random < charset.count {
                    result.append(charset[Int(random)])
                    remainingLength -= 1
                }
            }
        }

        return result
    }

    private func sha256(_ input: String) -> String {
        let inputData = Data(input.utf8)
        let hashedData = SHA256.hash(data: inputData)
        let hashString = hashedData.compactMap {
            String(format: "%02x", $0)
        }.joined()

        return hashString
    }
}

// MARK: - Errors

enum AuthError: Error, LocalizedError {
    case notAuthenticated
    case noRefreshToken
    case refreshFailed
    case appleSignInFailed

    var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "Not authenticated"
        case .noRefreshToken:
            return "No refresh token available"
        case .refreshFailed:
            return "Failed to refresh token"
        case .appleSignInFailed:
            return "Apple Sign In failed"
        }
    }
}

// MARK: - Apple Sign In Delegate

private class AppleSignInDelegate: NSObject, ASAuthorizationControllerDelegate, ASAuthorizationControllerPresentationContextProviding {
    let continuation: CheckedContinuation<User, Error>
    let nonce: String

    init(continuation: CheckedContinuation<User, Error>, nonce: String) {
        self.continuation = continuation
        self.nonce = nonce
    }

    func authorizationController(controller: ASAuthorizationController, didCompleteWithAuthorization authorization: ASAuthorization) {
        guard let appleIDCredential = authorization.credential as? ASAuthorizationAppleIDCredential else {
            continuation.resume(throwing: AuthError.appleSignInFailed)
            return
        }

        guard let identityTokenData = appleIDCredential.identityToken,
              let identityToken = String(data: identityTokenData, encoding: .utf8) else {
            continuation.resume(throwing: AuthError.appleSignInFailed)
            return
        }

        // Send to backend
        Task {
            do {
                let user = try await self.sendToBackend(
                    identityToken: identityToken,
                    email: appleIDCredential.email,
                    fullName: appleIDCredential.fullName
                )
                continuation.resume(returning: user)
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
        continuation.resume(throwing: error)
    }

    func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let window = windowScene.windows.first else {
            fatalError("No window available")
        }
        return window
    }

    private func sendToBackend(identityToken: String, email: String?, fullName: PersonNameComponents?) async throws -> User {
        let url = URL(string: "\(AppSettings.shared.baseURL)/auth/apple")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let fullNameString = fullName.flatMap { components in
            [components.givenName, components.familyName]
                .compactMap { $0 }
                .joined(separator: " ")
        }

        let body: [String: Any?] = [
            "id_token": identityToken,
            "email": email ?? "",
            "full_name": fullNameString
        ]

        request.httpBody = try? JSONSerialization.data(withJSONObject: body.compactMapValues { $0 })

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw AuthError.appleSignInFailed
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let tokenResponse = try decoder.decode(TokenResponse.self, from: data)

        // Save tokens
        KeychainManager.shared.saveToken(tokenResponse.accessToken, key: .accessToken)
        KeychainManager.shared.saveToken(tokenResponse.refreshToken, key: .refreshToken)
        KeychainManager.shared.saveToken(String(tokenResponse.user.id), key: .userId)

        return tokenResponse.user
    }
}
