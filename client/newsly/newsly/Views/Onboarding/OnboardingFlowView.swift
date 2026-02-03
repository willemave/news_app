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
                Color.black.opacity(0.2)
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

    private var introView: some View {
        VStack(alignment: .leading, spacing: 20) {
            Spacer()
            Image(systemName: "sparkles")
                .font(.system(size: 44, weight: .semibold))
                .foregroundColor(.blue)
            Text("Welcome to Newsly")
                .font(.largeTitle.bold())
            Text("Your personal inbox for long-form and short-form news. We’ll tune your feeds to match your interests.")
                .font(.body)
                .foregroundColor(.secondary)
            Spacer()
            Button("Continue") {
                viewModel.advanceToChoice()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(32)
    }

    private var choiceView: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Set up your feeds")
                .font(.title.bold())
            Text("Share what you want to read and we’ll find the best sources, or start with defaults.")
                .foregroundColor(.secondary)

            Button("Personalize my feeds") {
                viewModel.startPersonalized()
            }
            .buttonStyle(.borderedProminent)

            Button("Use defaults") {
                viewModel.chooseDefaults()
            }
            .buttonStyle(.bordered)

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.footnote)
                    .foregroundColor(.red)
            }

            Spacer()
        }
        .padding(32)
    }

    private var audioView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Tell us what you read")
                    .font(.title.bold())
                Text("We’ll record a short voice note and build your feed from it.")
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
                        .font(.footnote)
                        .foregroundColor(.red)
                }
            }
            .padding(32)
        }
        .task {
            await viewModel.startAudioCaptureIfNeeded()
        }
    }

    private var audioIntroCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: "mic.fill")
                    .font(.system(size: 28, weight: .semibold))
                    .foregroundColor(.blue)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Start speaking")
                        .font(.headline)
                    Text("Say what you’re interested in. We’ll stop at 30 seconds.")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                Spacer()
            }

            Button("Start recording") {
                Task { await viewModel.startAudioCapture() }
            }
            .buttonStyle(.borderedProminent)

            Button("Use defaults instead") {
                viewModel.chooseDefaults()
            }
            .buttonStyle(.bordered)
        }
        .padding(16)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var audioRecordingView: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "waveform")
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundColor(.red)
                Text("Listening • \(formattedAudioDuration)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Spacer()
            }

            Text("We’ll auto-stop at 30 seconds.")
                .font(.footnote)
                .foregroundColor(.secondary)

            Button("Stop and search") {
                Task { await viewModel.stopAudioCaptureAndDiscover() }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(16)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var audioTranscribingView: some View {
        HStack(spacing: 12) {
            ProgressView()
            Text("Transcribing your note…")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding(12)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var audioErrorView: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.orange)
                Text("We couldn’t record audio")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }

            Button("Try again") {
                Task { await viewModel.startAudioCapture() }
            }
            .buttonStyle(.borderedProminent)

            Button("Use defaults instead") {
                viewModel.chooseDefaults()
            }
            .buttonStyle(.bordered)
        }
        .padding(16)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var formattedAudioDuration: String {
        let minutes = viewModel.audioDurationSeconds / 60
        let seconds = viewModel.audioDurationSeconds % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    private var loadingView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Finding your feeds")
                    .font(.title.bold())
                Text("We’re searching across newsletters, podcasts, and Reddit.")
                    .foregroundColor(.secondary)

                if viewModel.discoveryLanes.isEmpty {
                    HStack(spacing: 12) {
                        ProgressView()
                        Text("Preparing search lanes…")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    .padding(12)
                    .background(.ultraThinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                } else {
                    ForEach(viewModel.discoveryLanes) { lane in
                        LaneStatusRow(lane: lane)
                    }
                }

                Text("This usually takes under a minute.")
                    .font(.footnote)
                    .foregroundColor(.secondary)

                if let message = viewModel.discoveryErrorMessage {
                    Text(message)
                        .font(.footnote)
                        .foregroundColor(.orange)
                }

                Button("Use defaults instead") {
                    viewModel.chooseDefaults()
                }
                .buttonStyle(.bordered)
            }
            .padding(32)
        }
    }

    private var suggestionsView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Top picks for you")
                    .font(.title.bold())
                Text("Review the suggested sources. You can edit these later.")
                    .foregroundColor(.secondary)

                if viewModel.substackSuggestions.isEmpty && viewModel.podcastSuggestions.isEmpty && viewModel.subredditSuggestions.isEmpty {
                    Text("We couldn’t find enough matches yet — we’ll start you with defaults.")
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

                Button("Finish setup") {
                    Task { await viewModel.completeOnboarding() }
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.isLoading)

                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.footnote)
                        .foregroundColor(.red)
                }
            }
            .padding(32)
        }
    }

    private var completionView: some View {
        VStack(alignment: .leading, spacing: 18) {
            Spacer()
            Text("Your inbox is ready")
                .font(.title.bold())
            if let response = viewModel.completionResponse {
                Text("\(response.inboxCountEstimate)+ unread news stories waiting.")
                    .font(.title3)
                Text("Long-form content: \(response.longformStatus.capitalized)")
                    .foregroundColor(.secondary)
            } else {
                Text("Your feeds are loading. You’ll start with at least 100 unread stories.")
                    .foregroundColor(.secondary)
            }
            Spacer()
            Button("Start reading") {
                if let response = viewModel.completionResponse {
                    onFinish(response)
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.completionResponse == nil)
        }
        .padding(32)
    }

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.headline)
            .padding(.top, 8)
    }
}

private struct LaneStatusRow: View {
    let lane: OnboardingDiscoveryLaneStatus

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: statusIcon)
                .foregroundColor(statusColor)
            VStack(alignment: .leading, spacing: 4) {
                Text(lane.name)
                    .font(.body)
                Text(statusLabel)
                    .font(.footnote)
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
        .padding(12)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
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
            return .blue
        case "completed":
            return .green
        case "failed":
            return .orange
        default:
            return .secondary
        }
    }
}

private struct SuggestionRow: View {
    let title: String
    let subtitle: String?
    let isSelected: Bool
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundColor(isSelected ? .blue : .secondary)
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.body)
                        .foregroundColor(.primary)
                    if let subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.footnote)
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
            }
            .padding(.vertical, 6)
        }
        .buttonStyle(.plain)
    }
}

private struct LoadingOverlay: View {
    let message: String

    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
                .scaleEffect(1.2)
            Text(message)
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding(24)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(radius: 10)
    }
}
