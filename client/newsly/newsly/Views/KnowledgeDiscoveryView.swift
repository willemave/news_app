//
//  KnowledgeDiscoveryView.swift
//  newsly
//

import SwiftUI

struct KnowledgeDiscoveryView: View {
    @ObservedObject var viewModel: DiscoveryViewModel
    let hasNewSuggestions: Bool
    @State private var safariTarget: SafariTarget?

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                if viewModel.isLoading && !viewModel.hasSuggestions {
                    DiscoveryLoadingStateView()
                } else if let error = viewModel.errorMessage, !viewModel.hasSuggestions {
                    DiscoveryErrorStateView(error: error) {
                        Task { await viewModel.loadSuggestions(force: true) }
                    }
                } else if !viewModel.hasSuggestions {
                    DiscoveryEmptyStateView(
                        isJobRunning: viewModel.isJobRunning,
                        runStatusDescription: viewModel.runStatusDescription,
                        currentJobStage: viewModel.currentJobStage
                    ) {
                        Task { await viewModel.refreshDiscovery() }
                    }
                } else {
                    suggestionContent
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .onAppear {
            Task { await viewModel.loadSuggestions() }
        }
        .refreshable {
            await viewModel.loadSuggestions(force: true)
        }
        .sheet(item: $safariTarget) { target in
            SafariView(url: target.url)
        }
    }

    // MARK: - Suggestion Content

    private var suggestionContent: some View {
        VStack(spacing: 0) {
            if viewModel.isJobRunning {
                runningJobBanner
                    .padding(.horizontal, Spacing.screenHorizontal)
                    .padding(.top, 12)
                    .padding(.bottom, 8)
            }

            if hasNewSuggestions && !viewModel.isJobRunning {
                newSuggestionsBanner
                    .padding(.horizontal, Spacing.screenHorizontal)
                    .padding(.top, 12)
                    .padding(.bottom, 8)
            }

            ForEach(displayRuns) { run in
                DiscoveryRunSection(
                    run: run,
                    onSubscribe: { suggestion in
                        Task { await viewModel.subscribe(suggestion) }
                    },
                    onAddItem: { suggestion in
                        Task { await viewModel.addItem(from: suggestion) }
                    },
                    onOpen: { suggestion in
                        openSuggestionURL(suggestion)
                    },
                    onDismiss: { suggestion in
                        Task { await viewModel.dismiss(suggestion) }
                    }
                )
            }

            if !viewModel.isJobRunning {
                generateMorePrompt
                    .padding(.top, 32)
                    .padding(.bottom, 40)
            }
        }
    }

    private var generateMorePrompt: some View {
        Button {
            Task { await viewModel.refreshDiscovery() }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "sparkles")
                    .font(.system(size: 14, weight: .regular))
                Text("Generate another")
                    .font(.subheadline)
            }
            .foregroundColor(.secondary)
        }
    }

    private var runningJobBanner: some View {
        HStack(spacing: 8) {
            ProgressView()
                .scaleEffect(0.7)

            Text("Discovering...")
                .font(.caption)
                .foregroundColor(.secondary)

            Spacer()

            Text(viewModel.runStatusDescription)
                .font(.caption2)
                .foregroundColor(Color(.tertiaryLabel))
        }
        .padding(.horizontal, Spacing.screenHorizontal)
        .padding(.vertical, 12)
    }

    private var newSuggestionsBanner: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(Color.accentColor)
                .frame(width: 6, height: 6)

            Text("New suggestions")
                .font(.caption)
                .foregroundColor(.secondary)

            Spacer()
        }
        .padding(.horizontal, Spacing.screenHorizontal)
        .padding(.vertical, 12)
    }

    // MARK: - Helpers

    private var displayRuns: [DiscoveryRunSuggestions] {
        if !viewModel.runs.isEmpty {
            return viewModel.runs
        }
        if viewModel.feeds.isEmpty && viewModel.podcasts.isEmpty && viewModel.youtube.isEmpty {
            return []
        }
        return [
            DiscoveryRunSuggestions(
                runId: -1,
                runStatus: viewModel.runStatus ?? "completed",
                runCreatedAt: viewModel.runCreatedAt ?? "",
                directionSummary: viewModel.directionSummary,
                feeds: viewModel.feeds,
                podcasts: viewModel.podcasts,
                youtube: viewModel.youtube
            )
        ]
    }

    private func openSuggestionURL(_ suggestion: DiscoverySuggestion) {
        let candidate = suggestion.itemURL ?? suggestion.siteURL ?? suggestion.feedURL
        guard let url = URL(string: candidate) else { return }
        safariTarget = SafariTarget(url: url)
    }
}

// MARK: - Safari Target

private struct SafariTarget: Identifiable {
    let id = UUID()
    let url: URL
}
