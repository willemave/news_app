//
//  KnowledgeDiscoveryView.swift
//  newsly
//

import SwiftUI

struct KnowledgeDiscoveryView: View {
    @ObservedObject var viewModel: DiscoveryViewModel
    let hasNewSuggestions: Bool
    @State private var safariTarget: SafariTarget?
    @State private var selectedSuggestion: DiscoverySuggestion?

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                // Editorial search bar
                editorialSearchBar
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 4)

                // Podcast search results (inline)
                if isPodcastSearchActive {
                    podcastSearchResults
                        .padding(.horizontal, Spacing.screenHorizontal)
                        .padding(.bottom, 8)
                }

                // Main content states
                if viewModel.isLoading && !viewModel.hasSuggestions {
                    DiscoveryLoadingStateView()
                } else if let error = viewModel.errorMessage, !viewModel.hasSuggestions {
                    DiscoveryErrorStateView(error: error) {
                        Task { await viewModel.loadSuggestions(force: true) }
                    }
                } else if !viewModel.hasSuggestions && viewModel.isJobRunning {
                    DiscoveryProcessingStateView(
                        runStatusDescription: viewModel.runStatusDescription,
                        currentJobStage: viewModel.currentJobStage
                    )
                } else if !viewModel.hasSuggestions {
                    DiscoveryEmptyStateView {
                        Task { await viewModel.refreshDiscovery() }
                    }
                } else {
                    suggestionContent
                }
            }
        }
        .background(Color.surfacePrimary)
        .onAppear {
            Task { await viewModel.loadSuggestions() }
        }
        .refreshable {
            await viewModel.loadSuggestions(force: true)
        }
        .sheet(item: $safariTarget) { target in
            SafariView(url: target.url)
        }
        .sheet(item: $selectedSuggestion) { suggestion in
            SuggestionDetailSheet(
                suggestion: suggestion,
                onSubscribe: {
                    Task { await viewModel.subscribe(suggestion) }
                },
                onAddItem: suggestion.hasItem ? {
                    Task { await viewModel.addItem(from: suggestion) }
                } : nil,
                onPreview: {
                    openSuggestionURL(suggestion)
                },
                onDismiss: {
                    Task { await viewModel.dismiss(suggestion) }
                }
            )
        }
    }

    // MARK: - Search Bar

    private var editorialSearchBar: some View {
        SearchBar(
            placeholder: "Search for content...",
            text: $viewModel.podcastSearchQuery,
            isLoading: viewModel.isPodcastSearchLoading,
            onSubmit: {
                Task { await viewModel.searchPodcastEpisodes() }
            },
            onClear: {
                viewModel.clearPodcastSearch()
            }
        )
    }

    // MARK: - Podcast Search Results

    private var isPodcastSearchActive: Bool {
        viewModel.isPodcastSearchLoading
            || viewModel.podcastSearchError != nil
            || (viewModel.hasPodcastSearchRun && !viewModel.podcastSearchResults.isEmpty)
            || (viewModel.hasPodcastSearchRun && viewModel.podcastSearchResults.isEmpty && !viewModel.isPodcastSearchLoading)
    }

    private var podcastSearchResults: some View {
        VStack(alignment: .leading, spacing: 8) {
            if viewModel.isPodcastSearchLoading {
                HStack(spacing: 8) {
                    ProgressView()
                        .controlSize(.small)
                    Text("Searching...")
                        .font(.editorialSubMeta)
                        .foregroundColor(.editorialSub)
                }
                .padding(.top, 8)
            } else if let error = viewModel.podcastSearchError {
                HStack {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.editorialSub)
                    Spacer()
                    Button("Retry") {
                        Task { await viewModel.retryPodcastSearch() }
                    }
                    .font(.caption)
                }
                .padding(.top, 8)
            } else if viewModel.hasPodcastSearchRun && viewModel.podcastSearchResults.isEmpty {
                Text("No episodes found. Try broader keywords.")
                    .font(.caption)
                    .foregroundColor(.editorialSub)
                    .padding(.top, 8)
            }

            if viewModel.hasPodcastSearchResults {
                VStack(spacing: 8) {
                    ForEach(viewModel.podcastSearchResults) { result in
                        PodcastEpisodeSearchCard(
                            result: result,
                            onAdd: {
                                Task { await viewModel.addPodcastEpisode(result) }
                            },
                            onOpen: {
                                openPodcastSearchResultURL(result)
                            }
                        )
                    }
                }
                .padding(.top, 4)
            }
        }
    }

    // MARK: - Suggestion Content

    private var suggestionContent: some View {
        VStack(spacing: 0) {
            if viewModel.isJobRunning {
                runningJobBanner
                    .padding(.top, 12)
                    .padding(.bottom, 8)
            }

            if hasNewSuggestions && !viewModel.isJobRunning {
                newSuggestionsBanner
                    .padding(.top, 12)
                    .padding(.bottom, 8)
            }

            ForEach(Array(displayRuns.enumerated()), id: \.element.id) { index, run in
                DiscoveryRunSection(
                    run: run,
                    isLatest: index == 0,
                    onSelect: { suggestion in
                        selectedSuggestion = suggestion
                    }
                )
            }

            if !viewModel.isJobRunning {
                generateMoreCard
                    .padding(.top, 32)
                    .padding(.bottom, 40)
                    .padding(.horizontal, Spacing.screenHorizontal)
            }
        }
    }

    private var generateMoreCard: some View {
        Button {
            Task { await viewModel.refreshDiscovery() }
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "sparkles")
                    .font(.system(size: 16, weight: .medium))
                    .foregroundColor(.editorialSub)

                Text("Generate More Suggestions")
                    .font(.editorialBody)
                    .foregroundColor(.editorialText)

                Spacer()

                Image(systemName: "arrow.right")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.editorialSub)
            }
            .padding(16)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.editorialBorder, lineWidth: 1)
            )
        }
        .buttonStyle(EditorialCardButtonStyle())
    }

    private var runningJobBanner: some View {
        HStack(spacing: 8) {
            ProgressView()
                .scaleEffect(0.7)

            Text("Discovering...")
                .font(.editorialSubMeta)
                .foregroundColor(.editorialSub)

            Spacer()

            Text(viewModel.runStatusDescription)
                .font(.editorialSubMeta)
                .foregroundColor(Color.textTertiary)
        }
        .padding(.horizontal, Spacing.screenHorizontal)
        .padding(.vertical, 12)
    }

    private var newSuggestionsBanner: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(Color.accentColor)
                .frame(width: 6, height: 6)

            Text("New suggestions available")
                .font(.editorialSubMeta)
                .foregroundColor(.editorialSub)

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

    private func openPodcastSearchResultURL(_ result: DiscoveryPodcastSearchResult) {
        guard let url = URL(string: result.episodeURL) else { return }
        safariTarget = SafariTarget(url: url)
    }
}

// MARK: - Podcast Episode Card (Editorial Style)

private struct PodcastEpisodeSearchCard: View {
    let result: DiscoveryPodcastSearchResult
    let onAdd: () -> Void
    let onOpen: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Metadata bar
            HStack(spacing: 6) {
                Image(systemName: "waveform")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(.orange)

                if let podcastTitle = result.podcastTitle, !podcastTitle.isEmpty {
                    Text(podcastTitle.uppercased())
                        .font(.editorialMeta)
                        .foregroundColor(.editorialSub)
                        .tracking(0.5)
                        .lineLimit(1)
                } else {
                    Text("PODCAST")
                        .font(.editorialMeta)
                        .foregroundColor(.editorialSub)
                        .tracking(0.5)
                }

                Spacer()
            }

            // Episode title as headline
            Text(result.title)
                .font(.editorialHeadline)
                .foregroundColor(.editorialText)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)

            // Action row
            HStack(spacing: 10) {
                Text(result.source ?? host(from: result.episodeURL))
                    .font(.editorialSubMeta)
                    .foregroundColor(Color.textTertiary)
                    .lineLimit(1)

                Spacer()

                Button(action: onAdd) {
                    Label("Add", systemImage: "plus")
                        .font(.caption.weight(.medium))
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
                .tint(.orange)

                Button(action: onOpen) {
                    Image(systemName: "safari")
                        .font(.caption)
                        .foregroundColor(.editorialSub)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(14)
        .background(Color.surfaceSecondary)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.editorialBorder, lineWidth: 1)
        )
        .cornerRadius(10)
    }

    private func host(from urlString: String) -> String {
        guard let url = URL(string: urlString), let host = url.host else {
            return urlString
        }
        return host.replacingOccurrences(of: "www.", with: "")
    }
}

// MARK: - Safari Target

private struct SafariTarget: Identifiable {
    let id = UUID()
    let url: URL
}
