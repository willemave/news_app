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
    @StateObject private var scraperViewModel = ScraperSettingsViewModel()
    @State private var tempHost: String = ""
    @State private var tempPort: String = ""
    @State private var showingAlert = false
    @State private var alertMessage = ""
    @State private var showMarkAllDialog = false
    @State private var isProcessingMarkAll = false
    @State private var showAddFeedSheet = false
    @State private var newFeedURL: String = ""
    @State private var newFeedName: String = ""
    @State private var newFeedType: String = "substack"
    @State private var selectedFeed: ScraperConfig?
    @State private var showFeedDetail = false
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

                Section(header: Text("Server Configuration")) {
                    HStack {
                        Text("Host")
                        Spacer()
                        TextField("localhost", text: $tempHost)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                            .frame(maxWidth: 200)
                    }
                    
                    HStack {
                        Text("Port")
                        Spacer()
                        TextField("8000", text: $tempPort)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .keyboardType(.numberPad)
                            .frame(maxWidth: 100)
                    }
                    
                    Toggle("Use HTTPS", isOn: $settings.useHTTPS)
                    
                    HStack {
                        Text("Current URL")
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(settings.baseURL)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Section(header: Text("Display Preferences")) {
                    Toggle("Show Read Articles", isOn: $settings.showReadContent)
                    Text("When enabled, both read and unread articles will be displayed")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Section(header: Text("Sources")) {
                    if scraperViewModel.isLoading {
                        ProgressView()
                    }

                    ForEach(scraperViewModel.configs) { config in
                        Button {
                            selectedFeed = config
                            showFeedDetail = true
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(config.displayName ?? (config.feedURL ?? "Feed"))
                                        .foregroundColor(.primary)
                                    Text(config.scraperType.capitalized)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    if let feedURL = config.feedURL {
                                        Text(feedURL)
                                            .font(.caption2)
                                            .foregroundColor(.secondary)
                                            .lineLimit(1)
                                    }
                                }
                                Spacer()
                                HStack(spacing: 4) {
                                    if config.isActive {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundColor(.green)
                                            .font(.caption)
                                    } else {
                                        Image(systemName: "circle")
                                            .foregroundColor(.secondary)
                                            .font(.caption)
                                    }
                                    Image(systemName: "chevron.right")
                                        .foregroundColor(.secondary)
                                        .font(.caption)
                                }
                            }
                        }
                        .swipeActions {
                            Button(role: .destructive) {
                                Task { await scraperViewModel.deleteConfig(config) }
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                    }

                    Button {
                        showAddFeedSheet = true
                    } label: {
                        Label("Add Feed", systemImage: "plus")
                    }

                    if let error = scraperViewModel.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.red)
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
                
                Section {
                    Button(action: saveSettings) {
                        HStack {
                            Spacer()
                            Text("Save Settings")
                                .foregroundColor(.white)
                            Spacer()
                        }
                    }
                    .listRowBackground(Color.blue)
                }
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
            .onAppear {
                tempHost = settings.serverHost
                tempPort = settings.serverPort
                Task { await scraperViewModel.loadConfigs() }
            }
            .sheet(isPresented: $showAddFeedSheet) {
                NavigationView {
                    Form {
                        Section(header: Text("Feed")) {
                            TextField("Feed URL", text: $newFeedURL)
                                .keyboardType(.URL)
                                .textInputAutocapitalization(.never)
                                .disableAutocorrection(true)
                            TextField("Display Name", text: $newFeedName)
                        }
                        Section(header: Text("Type")) {
                            Picker("Type", selection: $newFeedType) {
                                Text("Substack").tag("substack")
                                Text("Atom/RSS").tag("atom")
                                Text("Podcast").tag("podcast_rss")
                            }
                            .pickerStyle(.segmented)
                        }
                    }
                    .navigationTitle("Add Feed")
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { showAddFeedSheet = false }
                        }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Save") {
                                Task {
                                    await scraperViewModel.addConfig(
                                        scraperType: newFeedType,
                                        displayName: newFeedName.isEmpty ? nil : newFeedName,
                                        feedURL: newFeedURL
                                    )
                                    newFeedURL = ""
                                    newFeedName = ""
                                    showAddFeedSheet = false
                                }
                            }
                            .disabled(newFeedURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        }
                    }
                }
            }
            #if DEBUG
            .sheet(isPresented: $showingDebugMenu) {
                DebugMenuView()
                    .environmentObject(authViewModel)
            }
            #endif
            .sheet(isPresented: $showFeedDetail) {
                if let feed = selectedFeed {
                    FeedDetailView(viewModel: scraperViewModel, config: feed)
                }
            }
        }
    }
    
    private func saveSettings() {
        // Validate port number
        if let portNumber = Int(tempPort), portNumber > 0 && portNumber <= 65535 {
            settings.serverHost = tempHost.isEmpty ? "localhost" : tempHost
            settings.serverPort = tempPort.isEmpty ? "8000" : tempPort
            alertMessage = "Settings saved successfully"
            showingAlert = true
        } else {
            alertMessage = "Invalid port number. Please enter a number between 1 and 65535."
            showingAlert = true
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
