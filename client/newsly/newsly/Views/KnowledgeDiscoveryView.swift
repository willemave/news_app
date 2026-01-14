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
        Group {
            if viewModel.isLoading && !viewModel.hasSuggestions {
                HStack {
                    Spacer()
                    ProgressView()
                    Spacer()
                }
            } else if let error = viewModel.errorMessage, !viewModel.hasSuggestions {
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundColor(.red)
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.vertical, 24)
        } else if !viewModel.hasSuggestions {
            emptyState
        } else {
            suggestionList
        }
        }
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

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "sparkles")
                .font(.largeTitle)
                .foregroundColor(.secondary)
            Text("No discovery suggestions yet")
                .font(.headline)
                .foregroundColor(.secondary)
            Text("Tap refresh to queue a discovery run.")
                .font(.caption)
                .foregroundColor(.secondary)
            Button("Queue Discovery") {
                Task { await viewModel.refreshDiscovery() }
            }
            .buttonStyle(.bordered)
        }
        .frame(maxWidth: .infinity, alignment: .center)
        .padding(.vertical, 40)
    }

    private var suggestionList: some View {
        List {
            if hasNewSuggestions {
                Section {
                    HStack(spacing: 8) {
                        Image(systemName: "sparkles")
                            .foregroundColor(.yellow)
                        Text("New suggestions available")
                            .font(.footnote)
                            .foregroundColor(.secondary)
                    }
                }
            }

            ForEach(displayRuns) { run in
                Section(header: Text(runTitle(for: run.runCreatedAt))) {
                    if let summary = run.directionSummary, !summary.isEmpty {
                        Text(summary)
                            .font(.footnote)
                            .foregroundColor(.secondary)
                    }

                    if !run.feeds.isEmpty {
                        sectionLabel("Feeds")
                        ForEach(run.feeds) { suggestion in
                            DiscoverySuggestionRow(
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

                    if !run.podcasts.isEmpty {
                        sectionLabel("Podcasts")
                        ForEach(run.podcasts) { suggestion in
                            DiscoverySuggestionRow(
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

                    if !run.youtube.isEmpty {
                        sectionLabel("YouTube")
                        ForEach(run.youtube) { suggestion in
                            DiscoverySuggestionRow(
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
                }
            }
        }
        .listStyle(.insetGrouped)
    }

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

    private func sectionLabel(_ title: String) -> some View {
        Text(title)
            .font(.caption)
            .foregroundColor(.secondary)
            .textCase(nil)
            .padding(.top, 4)
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

private struct DiscoverySuggestionRow: View {
    let suggestion: DiscoverySuggestion
    let onSubscribe: () -> Void
    let onAddItem: (() -> Void)?
    let onOpen: () -> Void
    let onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(suggestion.displayTitle)
                .font(.headline)
                .foregroundColor(.primary)
                .lineLimit(2)

            if let subtitle = suggestion.displaySubtitle {
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(3)
            }

            Text(suggestion.primaryURL)
                .font(.caption2)
                .foregroundColor(.secondary)
                .lineLimit(1)

            HStack(spacing: 8) {
                if suggestion.canSubscribe {
                    Button(suggestion.subscribeLabel) {
                        onSubscribe()
                    }
                    .buttonStyle(.borderedProminent)
                }

                if let onAddItem {
                    Button(suggestion.addItemLabel) {
                        onAddItem()
                    }
                    .buttonStyle(.bordered)
                }

                Button("View") {
                    onOpen()
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(.vertical, 4)
        .swipeActions(edge: .trailing) {
            Button(role: .destructive) {
                onDismiss()
            } label: {
                Label("Dismiss", systemImage: "xmark")
            }
        }
    }
}

private struct SafariTarget: Identifiable {
    let id = UUID()
    let url: URL
}
