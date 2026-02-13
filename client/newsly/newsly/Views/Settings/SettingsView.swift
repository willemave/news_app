//
//  SettingsView.swift
//  newsly
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authViewModel: AuthenticationViewModel
    @ObservedObject private var settings = AppSettings.shared
    @State private var showingAlert = false
    @State private var alertMessage = ""
    @State private var showMarkAllDialog = false
    @State private var isProcessingMarkAll = false
    @State private var showingDebugMenu = false

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                accountSection
                SectionDivider()

                displayPreferencesSection
                SectionDivider()

                sourcesSection
                SectionDivider()

                readStatusSection

                #if DEBUG && targetEnvironment(simulator)
                SectionDivider()
                debugSection
                #endif

                Spacer(minLength: 40)
            }
        }
        .background(Color.surfacePrimary)
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
        .sheet(isPresented: $showingDebugMenu) {
            DebugMenuView()
                .environmentObject(authViewModel)
        }
    }

    // MARK: - Account Section

    private var accountSection: some View {
        VStack(spacing: 0) {
            SectionHeader(title: "Account")

            if case .authenticated(let user) = authViewModel.authState {
                AccountCard(user: user)

                RowDivider()

                Button {
                    authViewModel.logout()
                } label: {
                    SettingsRow(
                        icon: "rectangle.portrait.and.arrow.right",
                        iconColor: .statusDestructive,
                        title: "Sign Out"
                    ) {
                        EmptyView()
                    }
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Display Preferences Section

    private var displayPreferencesSection: some View {
        VStack(spacing: 0) {
            SectionHeader(title: "Display")

            SettingsToggleRow(
                icon: "eye",
                iconColor: .blue,
                title: "Show Read Articles",
                subtitle: "Display both read and unread",
                isOn: $settings.showReadContent
            )
        }
    }

    // MARK: - Sources Section

    private var sourcesSection: some View {
        VStack(spacing: 0) {
            SectionHeader(title: "Sources")

            NavigationLink {
                FeedSourcesView()
            } label: {
                SettingsRow(
                    icon: "list.bullet.rectangle",
                    iconColor: .blue,
                    title: "Feed Sources"
                )
            }
            .buttonStyle(.plain)

            RowDivider()

            NavigationLink {
                PodcastSourcesView()
            } label: {
                SettingsRow(
                    icon: "waveform",
                    iconColor: .purple,
                    title: "Podcast Sources"
                )
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - Read Status Section

    private var readStatusSection: some View {
        VStack(spacing: 0) {
            SectionHeader(title: "Actions")

            Button {
                showMarkAllDialog = true
            } label: {
                SettingsRow(
                    icon: "checkmark.circle",
                    iconColor: .green,
                    title: "Mark All As Read",
                    subtitle: "Choose content type to mark as read"
                ) {
                    if isProcessingMarkAll {
                        ProgressView()
                    } else {
                        EmptyView()
                    }
                }
            }
            .buttonStyle(.plain)
            .disabled(isProcessingMarkAll)
        }
    }

    // MARK: - Debug Section

    private var debugSection: some View {
        VStack(spacing: 0) {
            SectionHeader(title: "Debug")

            Button {
                showingDebugMenu = true
            } label: {
                SettingsRow(
                    icon: "ladybug",
                    iconColor: .red,
                    title: "Debug Menu",
                    subtitle: "Test authentication (Simulator)"
                ) {
                    EmptyView()
                }
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - Actions

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

// MARK: - Account Card

private struct AccountCard: View {
    let user: User

    var body: some View {
        HStack(spacing: 12) {
            // Avatar
            Circle()
                .fill(Color.accentColor.opacity(0.15))
                .frame(width: 44, height: 44)
                .overlay(
                    Text(user.email.prefix(1).uppercased())
                        .font(.headline)
                        .foregroundStyle(.tint)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text(user.fullName ?? user.email)
                    .font(.listTitle)
                    .foregroundStyle(Color.textPrimary)

                if user.fullName != nil {
                    Text(user.email)
                        .font(.listCaption)
                        .foregroundStyle(Color.textTertiary)
                }
            }

            Spacer()
        }
        .padding(.vertical, Spacing.rowVertical)
        .padding(.horizontal, Spacing.rowHorizontal)
    }
}

// MARK: - Navigation

// MARK: - Mark All Target

private enum MarkAllTarget: String, CaseIterable {
    case article
    case podcast
    case news

    var singularLabel: String {
        switch self {
        case .article: return "Article"
        case .podcast: return "Podcast"
        case .news: return "News item"
        }
    }

    var pluralLabel: String {
        switch self {
        case .article: return "Articles"
        case .podcast: return "Podcasts"
        case .news: return "News items"
        }
    }

    var buttonTitle: String {
        "Mark all \(pluralLabel.lowercased()) as read"
    }

    func description(for count: Int) -> String {
        count == 1 ? singularLabel.lowercased() : pluralLabel.lowercased()
    }
}
