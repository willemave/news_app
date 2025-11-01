//
//  DebugMenuView.swift
//  newsly
//
//  Debug menu for testing authentication without Apple Sign In
//  Only available in DEBUG builds
//

import SwiftUI

#if DEBUG
struct DebugMenuView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authViewModel: AuthenticationViewModel
    @State private var showingTokenInput = false
    @State private var accessToken = ""
    @State private var refreshToken = ""
    @State private var showingAlert = false
    @State private var alertMessage = ""

    var body: some View {
        NavigationView {
            List {
                Section(header: Text("Current Status")) {
                    HStack {
                        Text("Auth State")
                        Spacer()
                        authStateText
                    }

                    HStack {
                        Text("Access Token")
                        Spacer()
                        if KeychainManager.shared.getToken(key: .accessToken) != nil {
                            Text("Stored ✓").foregroundColor(.green)
                        } else {
                            Text("None").foregroundColor(.red)
                        }
                    }

                    HStack {
                        Text("Refresh Token")
                        Spacer()
                        if KeychainManager.shared.getToken(key: .refreshToken) != nil {
                            Text("Stored ✓").foregroundColor(.green)
                        } else {
                            Text("None").foregroundColor(.red)
                        }
                    }
                }

                Section(header: Text("Test Actions")) {
                    Button("Sign In with Stored Token") {
                        signInWithStoredToken()
                    }
                    .disabled(KeychainManager.shared.getToken(key: .accessToken) == nil)

                    Button("Manually Set Tokens") {
                        showingTokenInput = true
                    }

                    Button("Use Backend Test Token") {
                        useBackendTestToken()
                    }

                    Button("Clear All Tokens") {
                        clearTokens()
                    }
                    .foregroundColor(.red)

                    Button("Force Logout") {
                        authViewModel.logout()
                        alertMessage = "Logged out and cleared tokens"
                        showingAlert = true
                    }
                    .foregroundColor(.orange)
                }

                Section(header: Text("Instructions")) {
                    Text("""
                    **Testing Without Apple Sign In:**

                    1. Ensure backend is running (localhost:8000)
                    2. Generate FRESH token: ./scripts/test_auth_flow.sh
                    3. Copy the access token from output
                    4. Tap "Manually Set Tokens" immediately
                    5. Paste and save (tokens expire in 30 min)

                    **Note:** If you get "invalid or expired", generate a new token. The app validates tokens with the backend.
                    """)
                    .font(.caption)
                    .foregroundColor(.secondary)
                }

                Section(header: Text("Keychain Debug")) {
                    Button("View Stored Tokens") {
                        viewStoredTokens()
                    }
                }
            }
            .navigationTitle("🐛 Debug Menu")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") {
                        dismiss()
                    }
                }
            }
        }
        .onChange(of: authViewModel.authState) { oldValue, newValue in
            // Auto-dismiss when authentication succeeds
            if case .authenticated = newValue {
                dismiss()
            }
        }
        .sheet(isPresented: $showingTokenInput) {
            TokenInputView(
                accessToken: $accessToken,
                refreshToken: $refreshToken,
                onSave: {
                    saveTokensManually()
                }
            )
        }
        .alert("Debug Action", isPresented: $showingAlert) {
            Button("OK") { }
        } message: {
            Text(alertMessage)
        }
    }

    private var authStateText: some View {
        switch authViewModel.authState {
        case .loading:
            return Text("Loading...").foregroundColor(.orange)
        case .unauthenticated:
            return Text("Unauthenticated").foregroundColor(.red)
        case .authenticated(let user):
            return Text("Authenticated: \(user.email)").foregroundColor(.green)
        }
    }

    private func signInWithStoredToken() {
        guard KeychainManager.shared.getToken(key: .accessToken) != nil else {
            alertMessage = "No access token found in keychain"
            showingAlert = true
            return
        }

        // Validate token with backend
        Task {
            do {
                authViewModel.authState = .loading
                let user = try await AuthenticationService.shared.getCurrentUser()
                await MainActor.run {
                    authViewModel.authState = .authenticated(user)
                }
            } catch {
                await MainActor.run {
                    authViewModel.authState = .unauthenticated
                    alertMessage = "Token is invalid or expired: \(error.localizedDescription)"
                    showingAlert = true
                }
            }
        }
    }

    private func saveTokensManually() {
        guard !accessToken.isEmpty else {
            alertMessage = "Access token required"
            showingAlert = true
            return
        }

        // Save tokens to keychain
        KeychainManager.shared.saveToken(accessToken, key: .accessToken)

        if !refreshToken.isEmpty {
            KeychainManager.shared.saveToken(refreshToken, key: .refreshToken)
        }

        showingTokenInput = false

        // Validate token with backend
        Task {
            do {
                authViewModel.authState = .loading
                let user = try await AuthenticationService.shared.getCurrentUser()
                await MainActor.run {
                    authViewModel.authState = .authenticated(user)
                }
            } catch {
                await MainActor.run {
                    // Clear invalid token
                    KeychainManager.shared.clearAll()
                    authViewModel.authState = .unauthenticated
                    alertMessage = "Token is invalid or expired. Please generate a new one."
                    showingAlert = true
                }
            }
        }
    }

    private func useBackendTestToken() {
        // This would make an API call to a debug endpoint that returns a test token
        // For now, show instructions
        alertMessage = """
        Run this in terminal:

        cd /path/to/news_app
        ./scripts/test_auth_flow.sh

        Then use "Manually Set Tokens" to paste the token.
        """
        showingAlert = true
    }

    private func clearTokens() {
        KeychainManager.shared.clearAll()
        authViewModel.authState = .unauthenticated
        alertMessage = "All tokens cleared"
        showingAlert = true
    }

    private func viewStoredTokens() {
        var message = "Stored Tokens:\n\n"

        if let accessToken = KeychainManager.shared.getToken(key: .accessToken) {
            message += "Access: \(accessToken.prefix(50))...\n\n"
        } else {
            message += "Access: None\n\n"
        }

        if let refreshToken = KeychainManager.shared.getToken(key: .refreshToken) {
            message += "Refresh: \(refreshToken.prefix(50))..."
        } else {
            message += "Refresh: None"
        }

        alertMessage = message
        showingAlert = true
    }
}

struct TokenInputView: View {
    @Environment(\.dismiss) var dismiss
    @Binding var accessToken: String
    @Binding var refreshToken: String
    let onSave: () -> Void

    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Access Token (Required)")) {
                    TextEditor(text: $accessToken)
                        .frame(height: 100)
                        .font(.system(.caption, design: .monospaced))
                }

                Section(header: Text("Refresh Token (Optional)")) {
                    TextEditor(text: $refreshToken)
                        .frame(height: 100)
                        .font(.system(.caption, design: .monospaced))
                }

                Section {
                    Button("Save Tokens") {
                        onSave()
                    }
                    .frame(maxWidth: .infinity)
                    .disabled(accessToken.isEmpty)
                }
            }
            .navigationTitle("Enter Tokens")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
}
#endif
