//
//  FeedSourcesView.swift
//  newsly
//

import SwiftUI

struct FeedSourcesView: View {
    @StateObject private var viewModel = ScraperSettingsViewModel(filterTypes: ["substack", "atom", "youtube"])
    @State private var selectedConfig: ScraperConfig?
    @State private var showDetail = false
    @State private var showAddSheet = false
    @State private var newFeedURL: String = ""
    @State private var newFeedName: String = ""
    @State private var newFeedType: String = "substack"

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
                    showDetail = true
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
                        Task { await viewModel.deleteConfig(config) }
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                }
            }

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Feed Sources")
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
        .sheet(isPresented: $showDetail) {
            if let selectedConfig {
                FeedDetailView(viewModel: viewModel, config: selectedConfig)
            }
        }
        .sheet(isPresented: $showAddSheet) {
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
                            Text("YouTube").tag("youtube")
                        }
                        .pickerStyle(.segmented)
                    }
                }
                .navigationTitle("Add Feed")
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { showAddSheet = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Save") {
                            Task {
                                await viewModel.addConfig(
                                    scraperType: newFeedType,
                                    displayName: newFeedName.isEmpty ? nil : newFeedName,
                                    feedURL: newFeedURL
                                )
                                newFeedURL = ""
                                newFeedName = ""
                                newFeedType = "substack"
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
