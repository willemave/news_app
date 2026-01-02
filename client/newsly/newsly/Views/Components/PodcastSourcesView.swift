//
//  PodcastSourcesView.swift
//  newsly
//

import SwiftUI

struct PodcastSourcesView: View {
    @StateObject private var viewModel = ScraperSettingsViewModel(filterTypes: ["podcast_rss"])
    @State private var selectedConfig: ScraperConfig?
    @State private var showAddSheet = false
    @State private var newFeedURL: String = ""
    @State private var newFeedName: String = ""
    @State private var newLimit: String = ""
    @State private var localError: String?

    var body: some View {
        List {
            if viewModel.isLoading {
                HStack {
                    Spacer()
                    ProgressView()
                    Spacer()
                }
            }

            ForEach(viewModel.configs) { config in
                Button {
                    selectedConfig = config
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(config.displayName ?? (config.feedURL ?? "Podcast"))
                                .foregroundColor(.primary)
                            if let feedURL = config.feedURL {
                                Text(feedURL)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                                    .lineLimit(1)
                            }
                            if let limit = config.limit {
                                Text("Limit: \(limit)")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
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
                        Task { await viewModel.deleteConfig(config) }
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                }
            }

            if let error = viewModel.errorMessage ?? localError {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Podcast Sources")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showAddSheet = true
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .onAppear {
            Task { await viewModel.loadConfigs() }
        }
        .sheet(item: $selectedConfig) { selectedConfig in
            FeedDetailView(viewModel: viewModel, config: selectedConfig)
        }
        .sheet(isPresented: $showAddSheet) {
            NavigationView {
                Form {
                    Section(header: Text("Podcast")) {
                        TextField("Feed URL", text: $newFeedURL)
                            .keyboardType(.URL)
                            .textInputAutocapitalization(.never)
                            .disableAutocorrection(true)
                        TextField("Display Name", text: $newFeedName)
                        TextField("Limit (1-100, optional)", text: $newLimit)
                            .keyboardType(.numberPad)
                    }
                }
                .navigationTitle("Add Podcast Source")
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { showAddSheet = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Save") {
                            let trimmedLimit = newLimit.trimmingCharacters(in: .whitespacesAndNewlines)
                            let limitValue = Int(trimmedLimit)
                            if let limitValue, !(1...100).contains(limitValue) {
                                localError = "Limit must be between 1 and 100"
                                return
                            }
                            localError = nil
                            Task {
                                await viewModel.addConfig(
                                    scraperType: "podcast_rss",
                                    displayName: newFeedName.isEmpty ? nil : newFeedName,
                                    feedURL: newFeedURL,
                                    limit: limitValue
                                )
                                newFeedURL = ""
                                newFeedName = ""
                                newLimit = ""
                                showAddSheet = false
                            }
                        }
                        .disabled(newFeedURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
            }
        }
    }
}
