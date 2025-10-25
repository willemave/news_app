//
//  newslyApp.swift
//  newsly
//
//  Created by Willem Ave on 7/8/25.
//

import SwiftUI

@main
struct newslyApp: App {
    @StateObject private var authViewModel = AuthenticationViewModel()

    var body: some Scene {
        WindowGroup {
            Group {
                switch authViewModel.authState {
                case .authenticated(let user):
                    ContentView()
                        .environmentObject(authViewModel)
                        .withToast()
                case .unauthenticated:
                    AuthenticationView()
                        .environmentObject(authViewModel)
                case .loading:
                    LoadingView()
                }
            }
        }
    }
}
