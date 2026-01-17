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
                    loadingState
                } else if let error = viewModel.errorMessage, !viewModel.hasSuggestions {
                    errorState(error)
                } else if !viewModel.hasSuggestions {
                    emptyState
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

    // MARK: - Loading State

    private var loadingState: some View {
        VStack(spacing: 16) {
            Spacer()
                .frame(height: 100)

            ProgressView()

            Text("Loading...")
                .font(.subheadline)
                .foregroundColor(.secondary)

            Spacer()
                .frame(height: 200)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Error State

    private func errorState(_ error: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
                .frame(height: 100)

            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 32, weight: .light))
                .foregroundColor(.secondary)

            VStack(spacing: 6) {
                Text("Something went wrong")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)

                Text(error)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Button {
                Task { await viewModel.loadSuggestions(force: true) }
            } label: {
                Text("Try Again")
                    .font(.subheadline)
                    .foregroundColor(.accentColor)
            }
            .padding(.top, 4)

            Spacer()
                .frame(height: 200)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 0) {
            Spacer()
                .frame(height: 60)

            // Running job indicator (if applicable)
            if viewModel.isJobRunning {
                runningJobCard
                    .padding(.bottom, 32)
            }

            // Empty state content
            VStack(spacing: 24) {
                Image(systemName: "sparkles")
                    .font(.system(size: 40, weight: .light))
                    .foregroundColor(.secondary)

                VStack(spacing: 8) {
                    Text("Discover New Content")
                        .font(.title3)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)

                    Text("AI-powered suggestions based on your reading history")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }

                if !viewModel.isJobRunning {
                    Button {
                        Task { await viewModel.refreshDiscovery() }
                    } label: {
                        Text("Generate Suggestions")
                            .font(.subheadline)
                            .foregroundColor(.accentColor)
                    }
                    .padding(.top, 8)
                }
            }

            Spacer()
                .frame(height: 200)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Running Job Card

    private var runningJobCard: some View {
        VStack(spacing: 12) {
            HStack(spacing: 10) {
                ProgressView()

                VStack(alignment: .leading, spacing: 2) {
                    Text("Discovery in Progress")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)

                    Text(viewModel.runStatusDescription)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }

            // Progress stages - minimal dots
            HStack(spacing: 8) {
                ForEach(0..<4, id: \.self) { index in
                    Circle()
                        .fill(index <= viewModel.currentJobStage ? Color.primary : Color(.tertiaryLabel))
                        .frame(width: 6, height: 6)
                }
            }
        }
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
        .padding(.horizontal, 20)
    }

    // MARK: - Suggestion Content

    private var suggestionContent: some View {
        VStack(spacing: 0) {
            // Running job banner (if applicable)
            if viewModel.isJobRunning {
                runningJobBanner
                    .padding(.horizontal, 16)
                    .padding(.top, 12)
                    .padding(.bottom, 8)
            }

            // New suggestions banner
            if hasNewSuggestions && !viewModel.isJobRunning {
                newSuggestionsBanner
                    .padding(.horizontal, 16)
                    .padding(.top, 12)
                    .padding(.bottom, 8)
            }

            ForEach(displayRuns) { run in
                runSection(run)
            }

            // End of list prompt
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
        .padding(.horizontal, 16)
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
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    // MARK: - Run Section

    private func runSection(_ run: DiscoveryRunSuggestions) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // Section header
            VStack(alignment: .leading, spacing: 4) {
                Text(runTitle(for: run.runCreatedAt))
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
                    .textCase(.uppercase)
                    .tracking(0.5)

                if let summary = run.directionSummary, !summary.isEmpty {
                    Text(summary)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                        .truncationMode(.tail)
                        .padding(.top, 2)
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 24)
            .padding(.bottom, 16)

            // Type sections
            if !run.feeds.isEmpty {
                typeSectionHeader(title: "Feeds", icon: "doc.text", color: .blue, count: run.feeds.count)
                suggestionCards(run.feeds)
            }

            if !run.podcasts.isEmpty {
                typeSectionHeader(title: "Podcasts", icon: "waveform", color: .orange, count: run.podcasts.count)
                suggestionCards(run.podcasts)
            }

            if !run.youtube.isEmpty {
                typeSectionHeader(title: "YouTube", icon: "play.rectangle.fill", color: .red, count: run.youtube.count)
                suggestionCards(run.youtube)
            }
        }
    }

    private func typeSectionHeader(title: String, icon: String, color: Color, count: Int) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .regular))
                .foregroundColor(.secondary)

            Text(title)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.primary)

            Text("\(count)")
                .font(.caption)
                .foregroundColor(.secondary)
                .monospacedDigit()

            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.top, 20)
        .padding(.bottom, 12)
    }

    private func suggestionCards(_ suggestions: [DiscoverySuggestion]) -> some View {
        VStack(spacing: 12) {
            ForEach(suggestions) { suggestion in
                DiscoverySuggestionCard(
                    suggestion: suggestion,
                    onSubscribe: { Task { await viewModel.subscribe(suggestion) } },
                    onAddItem: suggestion.hasItem
                        ? { Task { await viewModel.addItem(from: suggestion) } }
                        : nil,
                    onOpen: { openSuggestionURL(suggestion) },
                    onDismiss: { Task { await viewModel.dismiss(suggestion) } }
                )
            }
        }
        .padding(.horizontal, 16)
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

    private func runTitle(for dateString: String) -> String {
        guard let date = parseDate(dateString) else { return "Discovery" }
        let calendar = Calendar.current
        let startOfWeek = calendar.dateInterval(of: .weekOfYear, for: date)?.start ?? date
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return "Week of \(formatter.string(from: startOfWeek))"
    }

    private func parseDate(_ dateString: String) -> Date? {
        let iso8601WithFractional = ISO8601DateFormatter()
        iso8601WithFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso8601WithFractional.date(from: dateString) {
            return date
        }

        let iso8601 = ISO8601DateFormatter()
        iso8601.formatOptions = [.withInternetDateTime]
        return iso8601.date(from: dateString)
    }

    private func openSuggestionURL(_ suggestion: DiscoverySuggestion) {
        let candidate = suggestion.itemURL ?? suggestion.siteURL ?? suggestion.feedURL
        guard let url = URL(string: candidate) else { return }
        safariTarget = SafariTarget(url: url)
    }
}

// MARK: - Suggestion Card

private struct DiscoverySuggestionCard: View {
    let suggestion: DiscoverySuggestion
    let onSubscribe: () -> Void
    let onAddItem: (() -> Void)?
    let onOpen: () -> Void
    let onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Content
            VStack(alignment: .leading, spacing: 8) {
                // Title
                Text(suggestion.displayTitle)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)

                // Subtitle/Rationale
                if let subtitle = suggestion.displaySubtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }

                // URL + Actions row
                HStack(spacing: 0) {
                    // URL
                    HStack(spacing: 4) {
                        Image(systemName: "link")
                            .font(.system(size: 10))
                        Text(formattedURL(suggestion.primaryURL))
                            .lineLimit(1)
                    }
                    .font(.caption2)
                    .foregroundColor(Color(.tertiaryLabel))

                    Spacer()

                    // Minimal action icons
                    HStack(spacing: 16) {
                        if suggestion.canSubscribe {
                            Button(action: onSubscribe) {
                                Image(systemName: "plus")
                                    .font(.system(size: 16, weight: .regular))
                                    .foregroundColor(.accentColor)
                            }
                        }

                        if let onAddItem {
                            Button(action: onAddItem) {
                                Image(systemName: "arrow.down")
                                    .font(.system(size: 16, weight: .regular))
                                    .foregroundColor(.secondary)
                            }
                        }

                        Button(action: onOpen) {
                            Image(systemName: "safari")
                                .font(.system(size: 16, weight: .regular))
                                .foregroundColor(.secondary)
                        }

                        Button(action: onDismiss) {
                            Image(systemName: "xmark")
                                .font(.system(size: 14, weight: .regular))
                                .foregroundColor(Color(.tertiaryLabel))
                        }
                    }
                }
                .padding(.top, 4)
            }
            .padding(16)
        }
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(12)
    }

    private func formattedURL(_ urlString: String) -> String {
        guard let url = URL(string: urlString),
              let host = url.host else {
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
