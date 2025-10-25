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

                    1. Start the backend server
                    2. Run: ./scripts/test_auth_flow.sh
                    3. Copy the access token from output
                    4. Tap "Manually Set Tokens"
                    5. Paste the token

                    **Or:** Use "Use Backend Test Token" to auto-generate tokens (requires backend running).
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

    private func saveTokensManually() {
        guard !accessToken.isEmpty else {
            alertMessage = "Access token required"
            showingAlert = true
            return
        }

        KeychainManager.shared.saveToken(accessToken, key: .accessToken)

        if !refreshToken.isEmpty {
            KeychainManager.shared.saveToken(refreshToken, key: .refreshToken)
        }

        // Create a mock user for testing
        let mockUser = User(
            id: 1,
            appleId: "debug.test.001",
            email: "debug@test.com",
            fullName: "Debug Test User",
            isAdmin: false,
            isActive: true,
            createdAt: Date(),
            updatedAt: Date()
        )

        authViewModel.authState = .authenticated(mockUser)

        alertMessage = "Tokens saved! App is now authenticated."
        showingAlert = true
        showingTokenInput = false
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
