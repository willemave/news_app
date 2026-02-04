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
    private let refreshCoordinator = RefreshCoordinator(cooldownSeconds: 10)

    /// Sign in with Apple
    @MainActor
    func signInWithApple() async throws -> AuthSession {
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

            // Keep delegate alive
            objc_setAssociatedObject(authController, "delegate", delegate, .OBJC_ASSOCIATION_RETAIN)

            authController.performRequests()
        }
    }

    /// Refresh access token using refresh token
    ///
    /// Implements refresh token rotation:
    /// - Sends current refresh token to backend
    /// - Receives new access token AND new refresh token
    /// - Saves both tokens (replaces old refresh token)
    /// - This allows active users to stay logged in indefinitely
    func refreshAccessToken() async throws -> String {
        if let task = await refreshCoordinator.activeTask() {
            return try await task.value
        }

        if let cached = await refreshCoordinator.cachedToken(
            accessToken: KeychainManager.shared.getToken(key: .accessToken)
        ) {
            return cached
        }

        await refreshCoordinator.markAttempt()

        let task = Task { [weak self] () throws -> String in
            defer {
                Task { [weak self] in
                    await self?.refreshCoordinator.clearTask()
                }
            }
            guard let self else { throw AuthError.refreshFailed }
            return try await self.performRefreshAccessToken()
        }

        await refreshCoordinator.setTask(task)
        return try await task.value
    }

    private func performRefreshAccessToken() async throws -> String {
        print("🔄 Starting token refresh...")

        guard let refreshToken = KeychainManager.shared.getToken(key: .refreshToken) else {
            print("❌ No refresh token found in keychain")
            throw AuthError.noRefreshToken
        }

        print("📤 Sending refresh request to backend...")
        let url = URL(string: "\(AppSettings.shared.baseURL)/auth/refresh")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = RefreshTokenRequest(refreshToken: refreshToken)
        request.httpBody = try? JSONEncoder().encode(body)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                print("❌ Invalid response from server")
                throw AuthError.serverError(statusCode: -1, message: "Invalid HTTP response")
            }

            print("📥 Refresh response status: \(httpResponse.statusCode)")

            switch httpResponse.statusCode {
            case 200:
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .iso8601

                let tokenResponse = try decoder.decode(AccessTokenResponse.self, from: data)

                // Save new access token AND new refresh token (token rotation)
                KeychainManager.shared.saveToken(tokenResponse.accessToken, key: .accessToken)
                KeychainManager.shared.saveToken(tokenResponse.refreshToken, key: .refreshToken)
                // Also save to shared UserDefaults for extension access
                SharedContainer.userDefaults.set(tokenResponse.accessToken, forKey: "accessToken")

                // Update OpenAI API key if provided
                if let openaiApiKey = tokenResponse.openaiApiKey {
                    print("🔑 [Refresh] OpenAI API key received from server (length: \(openaiApiKey.count))")
                    KeychainManager.shared.saveToken(openaiApiKey, key: .openaiApiKey)
                    // Verify the save
                    if let verified = KeychainManager.shared.getToken(key: .openaiApiKey) {
                        print("🔑 [Refresh] OpenAI API key verified in keychain (length: \(verified.count))")
                    } else {
                        print("❌ [Refresh] OpenAI API key FAILED to save to keychain!")
                    }
                } else {
                    print("⚠️ [Refresh] No OpenAI API key in token response")
                }

                print("✅ Token refresh successful - both tokens rotated")

                return tokenResponse.accessToken

            case 401, 403:
                // Refresh token is no longer valid; clear stored tokens so we do not loop
                KeychainManager.shared.deleteToken(key: .accessToken)
                KeychainManager.shared.deleteToken(key: .refreshToken)

                if let errorBody = String(data: data, encoding: .utf8) {
                    print("❌ Refresh token expired/invalid: \(errorBody)")
                }
                throw AuthError.refreshTokenExpired

            default:
                let errorBody = String(data: data, encoding: .utf8)
                print("❌ Refresh failed with status \(httpResponse.statusCode): \(errorBody ?? "<no body>")")
                throw AuthError.serverError(statusCode: httpResponse.statusCode, message: errorBody)
            }
        } catch let urlError as URLError {
            print("❌ Token refresh network error: \(urlError)")
            throw AuthError.networkError(urlError)
        } catch let authError as AuthError {
            throw authError
        } catch {
            print("❌ Token refresh error: \(error)")
            throw AuthError.refreshFailed
        }
    }

    /// Logout user (clear all tokens)
    func logout() {
        KeychainManager.shared.clearAll()
        SharedContainer.userDefaults.removeObject(forKey: "accessToken")
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

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.serverError(statusCode: -1, message: "Invalid HTTP response")
            }

            switch httpResponse.statusCode {
            case 200:
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .iso8601

                let user = try decoder.decode(User.self, from: data)
                return user
            case 401, 403:
                // Access token expired/invalid; clear it but keep refresh token for rotation
                KeychainManager.shared.deleteToken(key: .accessToken)
                throw AuthError.notAuthenticated
            default:
                let body = String(data: data, encoding: .utf8)
                throw AuthError.serverError(statusCode: httpResponse.statusCode, message: body)
            }
        } catch let urlError as URLError {
            throw AuthError.networkError(urlError)
        }
    }

    /// Create a fresh debug user (debug servers only).
    @MainActor
    func createDebugUser() async throws -> AuthSession {
        let url = URL(string: "\(AppSettings.shared.baseURL)\(APIEndpoints.authDebugNewUser)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw AuthError.serverError(statusCode: -1, message: "Invalid HTTP response")
            }

            switch httpResponse.statusCode {
            case 200:
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .iso8601
                let tokenResponse = try decoder.decode(TokenResponse.self, from: data)
                persistSessionTokens(tokenResponse)
                return AuthSession(user: tokenResponse.user, isNewUser: tokenResponse.isNewUser)
            case 404:
                throw AuthError.serverError(statusCode: 404, message: "Debug endpoint unavailable")
            default:
                let body = String(data: data, encoding: .utf8)
                throw AuthError.serverError(statusCode: httpResponse.statusCode, message: body)
            }
        } catch let urlError as URLError {
            throw AuthError.networkError(urlError)
        }
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
    case refreshTokenExpired
    case refreshFailed
    case serverError(statusCode: Int, message: String?)
    case networkError(Error)
    case appleSignInFailed

    var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "Not authenticated"
        case .noRefreshToken:
            return "No refresh token available"
        case .refreshTokenExpired:
            return "Refresh token expired"
        case .refreshFailed:
            return "Failed to refresh token"
        case .serverError(let statusCode, let message):
            return "Server error \(statusCode): \(message ?? "Unknown")"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .appleSignInFailed:
            return "Apple Sign In failed"
        }
    }
}

// MARK: - Apple Sign In Delegate

@MainActor
private class AppleSignInDelegate: NSObject, ASAuthorizationControllerDelegate, ASAuthorizationControllerPresentationContextProviding {
    let continuation: CheckedContinuation<AuthSession, Error>
    let nonce: String

    init(continuation: CheckedContinuation<AuthSession, Error>, nonce: String) {
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
                let session = try await self.sendToBackend(
                    identityToken: identityToken,
                    email: appleIDCredential.email,
                    fullName: appleIDCredential.fullName
                )
                continuation.resume(returning: session)
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

    private func sendToBackend(identityToken: String, email: String?, fullName: PersonNameComponents?) async throws -> AuthSession {
        let url = URL(string: "\(AppSettings.shared.baseURL)/auth/apple")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Extract full name if available
        let fullNameString: String? = fullName.flatMap { components in
            let parts = [components.givenName, components.familyName].compactMap { $0 }
            return parts.isEmpty ? nil : parts.joined(separator: " ")
        }

        // Build request body - only include non-empty values
        // Apple only provides email/name on FIRST sign-in, not subsequent sign-ins
        var body: [String: Any] = ["id_token": identityToken]

        if let email = email, !email.isEmpty {
            body["email"] = email
            print("📧 Sending email to backend: \(email)")
        } else {
            print("📧 No email from Apple - backend will extract from token")
        }

        if let fullName = fullNameString, !fullName.isEmpty {
            body["full_name"] = fullName
            print("👤 Sending full name to backend: \(fullName)")
        } else {
            print("👤 No full name from Apple - backend may extract from token")
        }

        print("🔐 Sending Apple Sign In request to: \(url)")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            print("❌ Invalid response from backend")
            throw AuthError.appleSignInFailed
        }

        guard httpResponse.statusCode == 200 else {
            print("❌ Backend returned status code: \(httpResponse.statusCode)")
            if let errorBody = String(data: data, encoding: .utf8) {
                print("❌ Error response: \(errorBody)")
            }
            throw AuthError.appleSignInFailed
        }

        print("✅ Apple Sign In successful - Status \(httpResponse.statusCode)")

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let tokenResponse = try decoder.decode(TokenResponse.self, from: data)

        persistSessionTokens(tokenResponse)

        return AuthSession(user: tokenResponse.user, isNewUser: tokenResponse.isNewUser)
    }
}

private func persistSessionTokens(_ tokenResponse: TokenResponse) {
    KeychainManager.shared.saveToken(tokenResponse.accessToken, key: .accessToken)
    KeychainManager.shared.saveToken(tokenResponse.refreshToken, key: .refreshToken)
    KeychainManager.shared.saveToken(String(tokenResponse.user.id), key: .userId)
    // Also save to shared UserDefaults for extension access
    SharedContainer.userDefaults.set(tokenResponse.accessToken, forKey: "accessToken")

    if let openaiApiKey = tokenResponse.openaiApiKey {
        print("🔑 [Auth] OpenAI API key received from server (length: \(openaiApiKey.count))")
        KeychainManager.shared.saveToken(openaiApiKey, key: .openaiApiKey)
        if let verified = KeychainManager.shared.getToken(key: .openaiApiKey) {
            print("🔑 [Auth] OpenAI API key verified in keychain (length: \(verified.count))")
        } else {
            print("❌ [Auth] OpenAI API key FAILED to save to keychain!")
        }
    } else {
        print("⚠️ [Auth] No OpenAI API key in token response from server")
    }
}

private actor RefreshCoordinator {
    private var refreshTask: Task<String, Error>?
    private var lastRefreshAttempt: Date?
    private let cooldownSeconds: TimeInterval

    init(cooldownSeconds: TimeInterval) {
        self.cooldownSeconds = cooldownSeconds
    }

    func activeTask() -> Task<String, Error>? {
        refreshTask
    }

    func setTask(_ task: Task<String, Error>) {
        refreshTask = task
    }

    func clearTask() {
        refreshTask = nil
    }

    func markAttempt() {
        lastRefreshAttempt = Date()
    }

    func cachedToken(accessToken: String?) -> String? {
        guard let lastRefreshAttempt,
              Date().timeIntervalSince(lastRefreshAttempt) < cooldownSeconds,
              let token = accessToken,
              !token.isEmpty else {
            return nil
        }
        return token
    }
}
