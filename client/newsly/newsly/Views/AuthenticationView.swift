//
//  AuthenticationView.swift
//  newsly
//
//  Created by Assistant on 10/25/25.
//

import SwiftUI
import AuthenticationServices

/// Login screen with Apple Sign In
struct AuthenticationView: View {
    @EnvironmentObject var authViewModel: AuthenticationViewModel

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // App logo or title
            VStack(spacing: 8) {
                Image(systemName: "newspaper.fill")
                    .font(.system(size: 60))
                    .foregroundColor(.blue)

                Text("Newsly")
                    .font(.largeTitle)
                    .fontWeight(.bold)
            }

            Spacer()

            // Sign in with Apple button
            SignInWithAppleButton(
                .signIn,
                onRequest: { request in
                    // Configuration handled by AuthenticationService
                },
                onCompletion: { result in
                    // Handled by AuthenticationService
                }
            )
            .signInWithAppleButtonStyle(.black)
            .frame(height: 50)
            .padding(.horizontal, 40)
            .onTapGesture {
                authViewModel.signInWithApple()
            }

            // Error message
            if let errorMessage = authViewModel.errorMessage {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.caption)
                    .padding(.horizontal, 40)
            }

            Spacer()
        }
        .padding()
    }
}

#Preview {
    AuthenticationView()
        .environmentObject(AuthenticationViewModel())
}
