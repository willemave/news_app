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
        VStack(spacing: 20) {
            Spacer()
                .frame(height: 100)

            DiscoveryLoadingIndicator()

            Text("Loading suggestions...")
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
                .frame(height: 80)

            ZStack {
                Circle()
                    .fill(Color.red.opacity(0.1))
                    .frame(width: 72, height: 72)

                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 28))
                    .foregroundColor(.red)
            }

            VStack(spacing: 6) {
                Text("Something went wrong")
                    .font(.headline)
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
                    .fontWeight(.medium)
            }
            .buttonStyle(.bordered)
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
            VStack(spacing: 20) {
                ZStack {
                    // Outer glow
                    Circle()
                        .fill(
                            RadialGradient(
                                colors: [Color.purple.opacity(0.15), Color.clear],
                                center: .center,
                                startRadius: 20,
                                endRadius: 60
                            )
                        )
                        .frame(width: 120, height: 120)

                    // Icon circle
                    Circle()
                        .fill(Color(.secondarySystemBackground))
                        .frame(width: 80, height: 80)

                    Image(systemName: "sparkles")
                        .font(.system(size: 32, weight: .medium))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [.purple, .blue],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                }

                VStack(spacing: 8) {
                    Text("Discover New Content")
                        .font(.title3)
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)

                    Text("AI-powered suggestions from your reading history")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }

                if !viewModel.isJobRunning {
                    Button {
                        Task { await viewModel.refreshDiscovery() }
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "wand.and.stars")
                            Text("Generate Suggestions")
                        }
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                        .padding(.horizontal, 24)
                        .padding(.vertical, 12)
                        .background(
                            LinearGradient(
                                colors: [.purple, .blue],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .cornerRadius(24)
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
        VStack(spacing: 16) {
            HStack(spacing: 12) {
                // Animated indicator
                DiscoveryPulseIndicator()

                VStack(alignment: .leading, spacing: 2) {
                    Text("Discovery in Progress")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)

                    Text(viewModel.runStatusDescription)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }

            // Progress stages
            HStack(spacing: 4) {
                ForEach(0..<4) { index in
                    DiscoveryStageIndicator(
                        stage: index,
                        currentStage: viewModel.currentJobStage
                    )
                }
            }
        }
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.purple.opacity(0.2), lineWidth: 1)
        )
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
        }
    }

    private var runningJobBanner: some View {
        HStack(spacing: 10) {
            DiscoveryPulseIndicator(size: 8)

            Text("Discovery running...")
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.purple)

            Spacer()

            Text(viewModel.runStatusDescription)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color.purple.opacity(0.08))
        .cornerRadius(10)
    }

    private var newSuggestionsBanner: some View {
        HStack(spacing: 8) {
            Image(systemName: "sparkles")
                .font(.caption)
                .foregroundColor(.yellow)

            Text("New suggestions available")
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.primary)

            Spacer()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color.yellow.opacity(0.1))
        .cornerRadius(10)
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
        HStack(spacing: 8) {
            // Icon badge
            ZStack {
                RoundedRectangle(cornerRadius: 6)
                    .fill(color.opacity(0.12))
                    .frame(width: 28, height: 28)

                Image(systemName: icon)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(color)
            }

            Text(title)
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(.primary)

            Text("\(count)")
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundColor(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color(.tertiarySystemFill))
                .cornerRadius(4)

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

    @State private var isPressed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Content
            VStack(alignment: .leading, spacing: 10) {
                // Title
                Text(suggestion.displayTitle)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)

                // Subtitle/Rationale
                if let subtitle = suggestion.displaySubtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                }

                // URL
                HStack(spacing: 4) {
                    Image(systemName: "link")
                        .font(.system(size: 9))
                    Text(formattedURL(suggestion.primaryURL))
                        .lineLimit(1)
                }
                .font(.caption2)
                .foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 12)

            // Divider
            Rectangle()
                .fill(Color(.separator).opacity(0.5))
                .frame(height: 0.5)

            // Actions
            HStack(spacing: 0) {
                if suggestion.canSubscribe {
                    actionButton(
                        title: suggestion.subscribeLabel,
                        icon: "plus.circle.fill",
                        isPrimary: true,
                        action: onSubscribe
                    )

                    if onAddItem != nil {
                        verticalDivider
                    }
                }

                if let onAddItem {
                    actionButton(
                        title: suggestion.addItemLabel,
                        icon: "arrow.down.circle",
                        isPrimary: false,
                        action: onAddItem
                    )
                }

                verticalDivider

                actionButton(
                    title: "View",
                    icon: "safari",
                    isPrimary: false,
                    action: onOpen
                )

                verticalDivider

                actionButton(
                    title: "Dismiss",
                    icon: "xmark",
                    isPrimary: false,
                    isDestructive: true,
                    action: onDismiss
                )
            }
            .frame(height: 44)
        }
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.04), radius: 8, x: 0, y: 2)
    }

    private var verticalDivider: some View {
        Rectangle()
            .fill(Color(.separator).opacity(0.5))
            .frame(width: 0.5)
    }

    private func actionButton(
        title: String,
        icon: String,
        isPrimary: Bool,
        isDestructive: Bool = false,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 11, weight: .medium))

                Text(title)
                    .font(.caption2)
                    .fontWeight(.medium)
            }
            .foregroundColor(
                isDestructive ? .red.opacity(0.8) :
                isPrimary ? .blue : .secondary
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func formattedURL(_ urlString: String) -> String {
        guard let url = URL(string: urlString),
              let host = url.host else {
            return urlString
        }
        return host.replacingOccurrences(of: "www.", with: "")
    }
}

// MARK: - Animated Indicators

private struct DiscoveryLoadingIndicator: View {
    @State private var isAnimating = false

    var body: some View {
        ZStack {
            // Outer ring
            Circle()
                .stroke(Color.purple.opacity(0.2), lineWidth: 3)
                .frame(width: 48, height: 48)

            // Animated arc
            Circle()
                .trim(from: 0, to: 0.3)
                .stroke(
                    LinearGradient(
                        colors: [.purple, .blue],
                        startPoint: .leading,
                        endPoint: .trailing
                    ),
                    style: StrokeStyle(lineWidth: 3, lineCap: .round)
                )
                .frame(width: 48, height: 48)
                .rotationEffect(.degrees(isAnimating ? 360 : 0))
                .animation(
                    .linear(duration: 1)
                    .repeatForever(autoreverses: false),
                    value: isAnimating
                )
        }
        .onAppear {
            isAnimating = true
        }
    }
}

private struct DiscoveryPulseIndicator: View {
    var size: CGFloat = 10
    @State private var isPulsing = false

    var body: some View {
        ZStack {
            // Pulse ring
            Circle()
                .fill(Color.purple.opacity(0.3))
                .frame(width: size * 2, height: size * 2)
                .scaleEffect(isPulsing ? 1.5 : 1)
                .opacity(isPulsing ? 0 : 0.6)

            // Core dot
            Circle()
                .fill(
                    LinearGradient(
                        colors: [.purple, .blue],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: size, height: size)
        }
        .onAppear {
            withAnimation(
                .easeInOut(duration: 1.2)
                .repeatForever(autoreverses: false)
            ) {
                isPulsing = true
            }
        }
    }
}

private struct DiscoveryStageIndicator: View {
    let stage: Int
    let currentStage: Int

    private var stageNames: [String] {
        ["Analyzing", "Searching", "Ranking", "Preparing"]
    }

    private var isActive: Bool { stage == currentStage }
    private var isComplete: Bool { stage < currentStage }

    private var stageTextColor: Color {
        if isActive {
            return .purple
        } else if isComplete {
            return .secondary
        } else {
            return Color(.tertiaryLabel)
        }
    }

    var body: some View {
        VStack(spacing: 4) {
            // Progress bar segment
            RoundedRectangle(cornerRadius: 2)
                .fill(
                    isComplete ? Color.purple :
                    isActive ? Color.purple.opacity(0.5) :
                    Color(.tertiarySystemFill)
                )
                .frame(height: 4)

            // Label
            Text(stageNames[stage])
                .font(.system(size: 9, weight: isActive ? .semibold : .regular))
                .foregroundColor(stageTextColor)
        }
    }
}

// MARK: - Safari Target

private struct SafariTarget: Identifiable {
    let id = UUID()
    let url: URL
}
