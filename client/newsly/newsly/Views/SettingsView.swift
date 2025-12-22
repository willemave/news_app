//
//  SettingsView.swift
//  newsly
//
//  Created by Assistant on 7/9/25.
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authViewModel: AuthenticationViewModel
    @ObservedObject private var settings = AppSettings.shared
    @State private var showingAlert = false
    @State private var alertMessage = ""
    @State private var showMarkAllDialog = false
    @State private var isProcessingMarkAll = false
    #if DEBUG
    @State private var showingDebugMenu = false
    #endif
    
    var body: some View {
        NavigationView {
            Form {
                // User section
                Section(header: Text("Account")) {
                    if case .authenticated(let user) = authViewModel.authState {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(user.email)
                                .font(.headline)
                            if let fullName = user.fullName {
                                Text(fullName)
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                        }

                        Button(role: .destructive) {
                            authViewModel.logout()
                        } label: {
                            Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                        }
                    }
                }

                Section(header: Text("Display Preferences")) {
                    Toggle("Show Read Articles", isOn: $settings.showReadContent)
                    Text("When enabled, both read and unread articles will be displayed")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Toggle("Use Card Stack", isOn: $settings.useLongFormCardStack)
                    Text("When off, displays articles and podcasts as a scrollable list")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Section(header: Text("Library")) {
                    NavigationLink {
                        FavoritesView()
                    } label: {
                        HStack {
                            Label("Favorites", systemImage: "star.fill")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundColor(.secondary)
                                .font(.caption)
                        }
                    }
                }

                Section(header: Text("Sources")) {
                    NavigationLink {
                        FeedSourcesView()
                    } label: {
                        HStack {
                            Label("Feed Sources", systemImage: "list.bullet.rectangle")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundColor(.secondary)
                                .font(.caption)
                        }
                    }

                    NavigationLink {
                        PodcastSourcesView()
                    } label: {
                        HStack {
                            Label("Podcast Sources", systemImage: "dot.radiowaves.left.and.right")
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundColor(.secondary)
                                .font(.caption)
                        }
                    }
                }

                Section(header: Text("Read Status")) {
                    Button {
                        showMarkAllDialog = true
                    } label: {
                        Label("Mark All As Read", systemImage: "checkmark.circle")
                    }
                    .disabled(isProcessingMarkAll)

                    if isProcessingMarkAll {
                        HStack {
                            Spacer()
                            ProgressView()
                            Spacer()
                        }
                    }

                    Text("Choose a content type to mark all unread items as read.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                #if DEBUG
                Section(header: Text("🐛 Debug Tools")) {
                    Button {
                        showingDebugMenu = true
                    } label: {
                        Label("Debug Menu", systemImage: "ladybug")
                    }

                    Text("Test authentication without Apple Sign In (Simulator only)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                #endif
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .alert("Settings", isPresented: $showingAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(alertMessage)
            }
            .confirmationDialog(
                "Mark all as read",
                isPresented: $showMarkAllDialog,
                titleVisibility: .visible
            ) {
                ForEach(MarkAllTarget.allCases, id: \.self) { target in
                    Button(target.buttonTitle) {
                        Task { await markAllContent(for: target) }
                    }
                }
                Button("Cancel", role: .cancel) { }
            }
            #if DEBUG
            .sheet(isPresented: $showingDebugMenu) {
                DebugMenuView()
                    .environmentObject(authViewModel)
            }
            #endif
        }
    }

    @MainActor
    private func markAllContent(for target: MarkAllTarget) async {
        guard !isProcessingMarkAll else { return }

        isProcessingMarkAll = true
        defer { isProcessingMarkAll = false }

        do {
            if let response = try await ContentService.shared.markAllAsRead(contentType: target.rawValue) {
                if response.markedCount > 0 {
                    await UnreadCountService.shared.refreshCounts()
                    alertMessage = "Marked \(response.markedCount) \(target.description(for: response.markedCount)) as read."
                } else {
                    alertMessage = "No unread \(target.description(for: 0)) found."
                }
            } else {
                alertMessage = "No unread \(target.description(for: 0)) found."
            }
        } catch let apiError as APIError {
            alertMessage = "Failed to mark as read: \(apiError.localizedDescription)"
        } catch {
            alertMessage = "Failed to mark as read: \(error.localizedDescription)"
        }

        showingAlert = true
    }
}

private enum MarkAllTarget: String, CaseIterable {
    case article
    case podcast
    case news

    var singularLabel: String {
        switch self {
        case .article:
            return "Article"
        case .podcast:
            return "Podcast"
        case .news:
            return "News item"
        }
    }

    var pluralLabel: String {
        switch self {
        case .article:
            return "Articles"
        case .podcast:
            return "Podcasts"
        case .news:
            return "News items"
        }
    }

    var buttonTitle: String {
        "Mark all \(pluralLabel.lowercased()) as read"
    }

    func description(for count: Int) -> String {
        if count == 1 {
            return singularLabel.lowercased()
        }
        return pluralLabel.lowercased()
    }
}
