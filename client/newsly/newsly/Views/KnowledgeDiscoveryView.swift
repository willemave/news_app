//
//  KnowledgeDiscoveryView.swift
//  newsly
//

import SwiftUI

struct KnowledgeDiscoveryView: View {
    @ObservedObject var viewModel: DiscoveryViewModel
    let hasNewSuggestions: Bool
    @State private var safariTarget: SafariTarget?
    @State private var isPodcastSearchExpanded = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                podcastSearchSection
                    .padding(.horizontal, Spacing.screenHorizontal)
                    .padding(.top, 12)
                    .padding(.bottom, 8)

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

    // MARK: - Podcast Search

    private var podcastSearchSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Collapsible header
            Button {
                withAnimation(.easeInOut(duration: 0.25)) {
                    isPodcastSearchExpanded.toggle()
                }
            } label: {
                HStack(spacing: 8) {
                    ZStack {
                        Circle()
                            .fill(Color.orange.opacity(0.12))
                            .frame(width: 28, height: 28)
                        Image(systemName: "waveform.badge.magnifyingglass")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundColor(.orange)
                    }

                    Text("Find Podcast Episodes")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Color.textTertiary)
                        .rotationEffect(.degrees(isPodcastSearchExpanded ? 90 : 0))
                }
                .padding(14)
            }
            .buttonStyle(.plain)

            if isPodcastSearchExpanded {
                VStack(alignment: .leading, spacing: 10) {
                    // Search field — chat-style bar
                    HStack(spacing: 8) {
                        Image(systemName: "magnifyingglass")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(.secondary)

                        TextField("Search episodes...", text: $viewModel.podcastSearchQuery)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .submitLabel(.search)
                            .onSubmit {
                                Task { await viewModel.searchPodcastEpisodes() }
                            }

                        if !viewModel.podcastSearchQuery.isEmpty {
                            Button {
                                viewModel.clearPodcastSearch()
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.system(size: 16))
                                    .foregroundColor(Color.textTertiary)
                            }
                            .buttonStyle(.plain)
                        }

                        // Inline submit
                        Button {
                            Task { await viewModel.searchPodcastEpisodes() }
                        } label: {
                            if viewModel.isPodcastSearchLoading {
                                ProgressView()
                                    .controlSize(.small)
                            } else {
                                Image(systemName: "arrow.right.circle.fill")
                                    .font(.system(size: 22))
                                    .foregroundColor(
                                        viewModel.podcastSearchQuery.trimmingCharacters(in: .whitespacesAndNewlines).count >= 2
                                            ? .accentColor : Color.textTertiary
                                    )
                            }
                        }
                        .buttonStyle(.plain)
                        .disabled(
                            viewModel.podcastSearchQuery.trimmingCharacters(in: .whitespacesAndNewlines).count < 2
                                || viewModel.isPodcastSearchLoading
                        )
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Color(.tertiarySystemGroupedBackground))
                    .cornerRadius(10)

                    // Status messages
                    if viewModel.isPodcastSearchLoading {
                        HStack(spacing: 8) {
                            ProgressView()
                                .controlSize(.small)
                            Text("Searching online sources...")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    } else if let error = viewModel.podcastSearchError {
                        HStack {
                            Text(error)
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Spacer()
                            Button("Retry") {
                                Task { await viewModel.retryPodcastSearch() }
                            }
                            .font(.caption)
                        }
                    } else if viewModel.hasPodcastSearchRun && viewModel.podcastSearchResults.isEmpty {
                        Text("No episodes found. Try broader keywords.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    // Results
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
                    }
                }
                .padding(.horizontal, 14)
                .padding(.bottom, 14)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(12)
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
                    .font(.system(size: 18, weight: .medium))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [.purple, .blue],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )

                VStack(alignment: .leading, spacing: 2) {
                    Text("Generate More Suggestions")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                    Text("Discover new content based on your interests")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Color.textTertiary)
            }
            .padding(14)
            .background(Color(.secondarySystemGroupedBackground))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [6, 4]))
                    .foregroundColor(Color.primary.opacity(0.1))
            )
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
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

    private func openPodcastSearchResultURL(_ result: DiscoveryPodcastSearchResult) {
        guard let url = URL(string: result.episodeURL) else { return }
        safariTarget = SafariTarget(url: url)
    }
}

// MARK: - Podcast Episode Card

private struct PodcastEpisodeSearchCard: View {
    let result: DiscoveryPodcastSearchResult
    let onAdd: () -> Void
    let onOpen: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Waveform icon
            ZStack {
                Circle()
                    .fill(Color.orange.opacity(0.12))
                    .frame(width: 36, height: 36)
                Image(systemName: "waveform")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(.orange)
            }
            .padding(.top, 2)

            VStack(alignment: .leading, spacing: 6) {
                Text(result.title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)

                if let podcastTitle = result.podcastTitle, !podcastTitle.isEmpty {
                    Text(podcastTitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }

                if let snippet = result.snippet, !snippet.isEmpty {
                    Text(snippet)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }

                HStack(spacing: 8) {
                    Text(result.source ?? host(from: result.episodeURL))
                        .font(.caption2)
                        .foregroundColor(Color.textTertiary)
                        .lineLimit(1)

                    Spacer()

                    Button(action: onAdd) {
                        Label("Add", systemImage: "plus")
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .tint(.orange)

                    Button(action: onOpen) {
                        Label("Open", systemImage: "safari")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                    .controlSize(.small)
                }
            }
        }
        .padding(12)
        .background(Color(.tertiarySystemGroupedBackground))
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
