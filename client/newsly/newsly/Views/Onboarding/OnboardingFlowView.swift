//
//  OnboardingFlowView.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import SwiftUI

struct OnboardingFlowView: View {
    @StateObject private var viewModel: OnboardingViewModel
    private let onFinish: (OnboardingCompleteResponse) -> Void

    init(user: User, onFinish: @escaping (OnboardingCompleteResponse) -> Void) {
        _viewModel = StateObject(wrappedValue: OnboardingViewModel(user: user))
        self.onFinish = onFinish
    }

    var body: some View {
        ZStack {
            content
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(UIColor.systemBackground))
            if viewModel.isLoading {
                Color.black.opacity(0.15)
                    .ignoresSafeArea()
                LoadingOverlay(message: viewModel.loadingMessage)
            }
        }
        .task {
            await viewModel.resumeDiscoveryIfNeeded()
        }
    }

    @ViewBuilder
    private var content: some View {
        switch viewModel.step {
        case .intro:
            introView
        case .choice:
            choiceView
        case .audio:
            audioView
        case .loading:
            loadingView
        case .suggestions:
            suggestionsView
        case .done:
            completionView
        }
    }

    // MARK: - Intro

    private var introView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Spacer()
            Image(systemName: "sparkles")
                .font(.system(size: 36, weight: .medium))
                .foregroundColor(.accentColor)
            Text("Welcome to Newsly")
                .font(.title2.bold())
            Text("Your personal inbox for long-form and short-form news. We'll tune your feeds to match your interests.")
                .font(.callout)
                .foregroundColor(.secondary)
            Spacer()
            primaryButton("Continue") {
                viewModel.advanceToChoice()
            }
        }
        .padding(24)
    }

    // MARK: - Choice

    private var choiceView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Set up your feeds")
                .font(.title2.bold())
            Text("Share what you want to read and we'll find the best sources, or start with defaults.")
                .font(.callout)
                .foregroundColor(.secondary)

            Spacer().frame(height: 8)

            primaryButton("Personalize my feeds") {
                viewModel.startPersonalized()
            }

            secondaryButton("Use defaults") {
                viewModel.chooseDefaults()
            }

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
            }

            Spacer()
        }
        .padding(24)
    }

    // MARK: - Audio

    private var audioView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Tell us what you read")
                    .font(.title2.bold())
                Text("We'll record a short voice note and build your feed from it.")
                    .font(.callout)
                    .foregroundColor(.secondary)

                switch viewModel.audioState {
                case .idle:
                    audioIntroCard
                case .recording:
                    audioRecordingView
                case .transcribing:
                    audioTranscribingView
                case .error:
                    audioErrorView
                }

                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                }
            }
            .padding(24)
        }
        .task {
            await viewModel.startAudioCaptureIfNeeded()
        }
    }

    private var audioIntroCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                Image(systemName: "mic.fill")
                    .font(.title3)
                    .foregroundColor(.accentColor)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Start speaking")
                        .font(.callout.weight(.medium))
                    Text("Say what you're interested in. We'll stop at 30s.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
            }

            primaryButton("Start recording") {
                Task { await viewModel.startAudioCapture() }
            }

            secondaryButton("Use defaults instead") {
                viewModel.chooseDefaults()
            }
        }
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var audioRecordingView: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "waveform")
                    .font(.body.weight(.medium))
                    .foregroundColor(.red)
                Text("Listening \(formattedAudioDuration)")
                    .font(.callout)
                    .foregroundColor(.secondary)
                Spacer()
            }

            Text("Auto-stops at 30 seconds.")
                .font(.caption)
                .foregroundColor(.secondary)

            primaryButton("Stop and search") {
                Task { await viewModel.stopAudioCaptureAndDiscover() }
            }
        }
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var audioTranscribingView: some View {
        HStack(spacing: 10) {
            ProgressView()
            Text("Transcribing...")
                .font(.callout)
                .foregroundColor(.secondary)
        }
        .padding(14)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var audioErrorView: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.callout)
                    .foregroundColor(.orange)
                Text("We couldn't record audio")
                    .font(.callout)
                    .foregroundColor(.secondary)
            }

            primaryButton("Try again") {
                Task { await viewModel.startAudioCapture() }
            }

            secondaryButton("Use defaults instead") {
                viewModel.chooseDefaults()
            }
        }
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var formattedAudioDuration: String {
        let minutes = viewModel.audioDurationSeconds / 60
        let seconds = viewModel.audioDurationSeconds % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    // MARK: - Loading / Discovery

    private var loadingView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Finding your feeds")
                    .font(.title2.bold())
                Text("Searching newsletters, podcasts, and Reddit.")
                    .font(.callout)
                    .foregroundColor(.secondary)

                if viewModel.discoveryLanes.isEmpty {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Preparing search lanes...")
                            .font(.callout)
                            .foregroundColor(.secondary)
                    }
                    .padding(14)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                } else {
                    ForEach(viewModel.discoveryLanes) { lane in
                        LaneStatusRow(lane: lane)
                    }
                }

                Text("This usually takes under a minute.")
                    .font(.caption)
                    .foregroundColor(.secondary)

                if let message = viewModel.discoveryErrorMessage {
                    Text(message)
                        .font(.caption)
                        .foregroundColor(.orange)
                }

                secondaryButton("Use defaults instead") {
                    viewModel.chooseDefaults()
                }
            }
            .padding(24)
        }
    }

    // MARK: - Suggestions

    private var suggestionsView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Top picks for you")
                    .font(.title2.bold())
                Text("Review the suggested sources. You can edit these later.")
                    .font(.callout)
                    .foregroundColor(.secondary)
                    .padding(.bottom, 4)

                if viewModel.substackSuggestions.isEmpty && viewModel.podcastSuggestions.isEmpty && viewModel.subredditSuggestions.isEmpty {
                    Text("We couldn't find enough matches yet — we'll start you with defaults.")
                        .font(.callout)
                        .foregroundColor(.secondary)
                }

                if !viewModel.substackSuggestions.isEmpty {
                    sectionHeader("Substacks & Feeds")
                    ForEach(viewModel.substackSuggestions, id: \.stableKey) { suggestion in
                        SuggestionRow(
                            title: suggestion.displayTitle,
                            subtitle: suggestion.rationale,
                            isSelected: viewModel.selectedSourceKeys.contains(suggestion.feedURL ?? "")
                        ) {
                            viewModel.toggleSource(suggestion)
                        }
                    }
                }

                if !viewModel.podcastSuggestions.isEmpty {
                    sectionHeader("Podcasts")
                    ForEach(viewModel.podcastSuggestions, id: \.stableKey) { suggestion in
                        SuggestionRow(
                            title: suggestion.displayTitle,
                            subtitle: suggestion.rationale,
                            isSelected: viewModel.selectedSourceKeys.contains(suggestion.feedURL ?? "")
                        ) {
                            viewModel.toggleSource(suggestion)
                        }
                    }
                }

                if !viewModel.subredditSuggestions.isEmpty {
                    sectionHeader("Reddit")
                    ForEach(viewModel.subredditSuggestions, id: \.stableKey) { suggestion in
                        SuggestionRow(
                            title: suggestion.displayTitle,
                            subtitle: suggestion.rationale,
                            isSelected: viewModel.selectedSubreddits.contains(suggestion.subreddit ?? "")
                        ) {
                            viewModel.toggleSubreddit(suggestion)
                        }
                    }
                }

                Spacer().frame(height: 8)

                primaryButton("Finish setup") {
                    Task { await viewModel.completeOnboarding() }
                }
                .disabled(viewModel.isLoading)

                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                }
            }
            .padding(24)
        }
    }

    // MARK: - Completion

    private var completionView: some View {
        VStack(alignment: .leading, spacing: 14) {
            Spacer()
            Image(systemName: "checkmark.circle")
                .font(.system(size: 36, weight: .medium))
                .foregroundColor(.green)
            Text("Your inbox is ready")
                .font(.title2.bold())
            if let response = viewModel.completionResponse {
                Text("\(response.inboxCountEstimate)+ unread stories waiting.")
                    .font(.callout)
                Text("Long-form: \(response.longformStatus.capitalized)")
                    .font(.callout)
                    .foregroundColor(.secondary)
            } else {
                Text("Your feeds are loading. You'll start with at least 100 unread stories.")
                    .font(.callout)
                    .foregroundColor(.secondary)
            }
            Spacer()
            primaryButton("Start reading") {
                if let response = viewModel.completionResponse {
                    onFinish(response)
                }
            }
            .disabled(viewModel.completionResponse == nil)
        }
        .padding(24)
    }

    // MARK: - Shared Components

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.subheadline.weight(.semibold))
            .foregroundColor(.secondary)
            .padding(.top, 12)
    }

    private func primaryButton(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.callout.weight(.semibold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .foregroundColor(.white)
                .background(Color.accentColor)
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }

    private func secondaryButton(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.callout.weight(.medium))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .foregroundColor(.primary)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Lane Status Row

private struct LaneStatusRow: View {
    let lane: OnboardingDiscoveryLaneStatus

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: statusIcon)
                .font(.callout)
                .foregroundColor(statusColor)
                .frame(width: 20)
            VStack(alignment: .leading, spacing: 2) {
                Text(lane.name)
                    .font(.callout)
                Text(statusLabel)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 14)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var statusLabel: String {
        switch lane.status {
        case "processing":
            return "Searching"
        case "completed":
            return "Done"
        case "failed":
            return "Failed"
        default:
            return "Queued"
        }
    }

    private var statusIcon: String {
        switch lane.status {
        case "processing":
            return "hourglass"
        case "completed":
            return "checkmark.circle.fill"
        case "failed":
            return "exclamationmark.triangle.fill"
        default:
            return "circle"
        }
    }

    private var statusColor: Color {
        switch lane.status {
        case "processing":
            return .accentColor
        case "completed":
            return .green
        case "failed":
            return .orange
        default:
            return .secondary
        }
    }
}

// MARK: - Suggestion Row

private struct SuggestionRow: View {
    let title: String
    let subtitle: String?
    let isSelected: Bool
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.body)
                    .foregroundColor(isSelected ? .accentColor : Color(.tertiaryLabel))
                    .padding(.top, 1)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.callout.weight(.medium))
                        .foregroundColor(.primary)
                    if let subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(2)
                    }
                }
                Spacer()
            }
            .padding(.vertical, 8)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Loading Overlay

private struct LoadingOverlay: View {
    let message: String

    var body: some View {
        VStack(spacing: 10) {
            ProgressView()
            Text(message)
                .font(.callout)
                .foregroundColor(.secondary)
        }
        .padding(20)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .shadow(color: .black.opacity(0.08), radius: 8, x: 0, y: 4)
    }
}
