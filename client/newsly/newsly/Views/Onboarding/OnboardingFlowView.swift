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
            WatercolorBackground(energy: 0.15)

            content
                .frame(maxWidth: .infinity, maxHeight: .infinity)

            if viewModel.isLoading {
                Color.black.opacity(0.15)
                    .ignoresSafeArea()
                LoadingOverlay(message: viewModel.loadingMessage)
            }
        }
        .preferredColorScheme(.light)
        .onChange(of: viewModel.completionResponse) { _, response in
            if let response {
                onFinish(response)
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
            choiceView
                .transition(.opacity)
        case .choice:
            choiceView
                .transition(.opacity)
        case .audio:
            audioView
                .transition(.opacity)
        case .loading:
            loadingView
                .transition(.opacity)
        case .suggestions:
            suggestionsView
                .transition(.opacity)
        }
    }

    // MARK: - Choice

    private var choiceView: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 24) {
                ZStack {
                    Circle()
                        .fill(Color.watercolorSlate.opacity(0.08))
                        .frame(width: 88, height: 88)
                    Image(systemName: "slider.horizontal.3")
                        .font(.system(size: 32, weight: .medium))
                        .foregroundColor(.watercolorSlate)
                }

                VStack(spacing: 10) {
                    Text("Set up your feeds")
                        .font(.title2.bold())
                        .foregroundColor(.watercolorSlate)
                    Text("Share what you read and we'll\ncurate the best sources for you.")
                        .font(.callout)
                        .foregroundColor(.watercolorSlate.opacity(0.6))
                        .multilineTextAlignment(.center)
                }
            }

            Spacer()

            twitterUsernameCard

            Spacer()

            VStack(spacing: 10) {
                choiceCard(
                    icon: "mic.fill",
                    title: "Personalize with voice",
                    subtitle: "Tell us your interests in 30 seconds",
                    isPrimary: true
                ) {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        viewModel.startPersonalized()
                    }
                }

                choiceCard(
                    icon: "wand.and.stars",
                    title: "Start with defaults",
                    subtitle: "We'll pick popular tech & news feeds",
                    isPrimary: false
                ) {
                    viewModel.chooseDefaults()
                }
            }

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.top, 8)
            }
        }
        .padding(24)
        .padding(.bottom, 8)
    }

    private func choiceCard(
        icon: String,
        title: String,
        subtitle: String,
        isPrimary: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: icon)
                    .font(.body.weight(.medium))
                    .foregroundColor(isPrimary ? .white : .watercolorSlate)
                    .frame(width: 36, height: 36)
                    .background(isPrimary ? Color.watercolorSlate : Color.watercolorSlate.opacity(0.1))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.callout.weight(.semibold))
                        .foregroundColor(.watercolorSlate)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.watercolorSlate.opacity(0.6))
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.watercolorSlate.opacity(0.4))
            }
            .padding(16)
            .background(Color.white.opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Audio

    private var audioView: some View {
        VStack(spacing: 0) {
            VStack(spacing: 8) {
                Text("Tell us what you read")
                    .font(.title2.bold())
                    .foregroundColor(.watercolorSlate)
                Text("Speak naturally about your interests.")
                    .font(.callout)
                    .foregroundColor(.watercolorSlate.opacity(0.6))
            }
            .padding(.top, 48)

            Spacer()

            if viewModel.audioState == .transcribing {
                audioProcessingView
            } else {
                OnboardingMicButton(
                    audioState: viewModel.audioState,
                    durationSeconds: viewModel.audioDurationSeconds,
                    onStart: { Task { await viewModel.startAudioCapture() } },
                    onStop: { Task { await viewModel.stopAudioCaptureAndDiscover() } }
                )
            }

            Spacer()

            if viewModel.audioState != .transcribing {
                Button("Skip") {
                    viewModel.chooseDefaults()
                }
                .font(.callout)
                .foregroundColor(.watercolorSlate.opacity(0.5))
                .padding(.bottom, 16)
            }

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.bottom, 8)
            }
        }
        .padding(.horizontal, 24)
        .task {
            await viewModel.startAudioCaptureIfNeeded()
        }
    }

    private var audioProcessingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.2)
                .tint(.watercolorSlate)
            Text("Processing your interests...")
                .font(.callout)
                .foregroundColor(.watercolorSlate.opacity(0.6))
        }
    }

    // MARK: - Loading / Discovery

    private var loadingView: some View {
        VStack(spacing: 0) {
            VStack(spacing: 8) {
                Text("Finding your feeds")
                    .font(.title2.bold())
                    .foregroundColor(.watercolorSlate)
                Text("Searching newsletters, podcasts, and Reddit.")
                    .font(.callout)
                    .foregroundColor(.watercolorSlate.opacity(0.6))
            }
            .frame(maxWidth: .infinity, alignment: .center)
            .padding(.top, 48)

            Spacer()

            VStack(spacing: 16) {
                if viewModel.discoveryLanes.isEmpty {
                    ProgressView()
                        .scaleEffect(1.2)
                        .tint(.watercolorSlate)
                    Text("Preparing search...")
                        .font(.callout)
                        .foregroundColor(.watercolorSlate.opacity(0.6))
                } else {
                    VStack(spacing: 12) {
                        ForEach(viewModel.discoveryLanes) { lane in
                            LaneStatusRow(lane: lane)
                        }
                    }
                    .padding(20)
                    .glassCard(cornerRadius: 20)
                }
            }

            Spacer()

            VStack(spacing: 12) {
                Text("Usually takes under a minute")
                    .font(.caption)
                    .foregroundColor(.watercolorSlate.opacity(0.5))

                if let message = viewModel.discoveryErrorMessage {
                    Text(message)
                        .font(.caption)
                        .foregroundColor(.orange)
                }

                Button("Use defaults instead") {
                    viewModel.chooseDefaults()
                }
                .font(.callout)
                .foregroundColor(.watercolorSlate.opacity(0.5))
            }
            .padding(.bottom, 16)
        }
        .padding(.horizontal, 24)
    }

    // MARK: - Suggestions

    private var suggestionsView: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Your picks")
                            .font(.title2.bold())
                            .foregroundColor(.watercolorSlate)
                        Text("Tap to deselect any you don't want.")
                            .font(.callout)
                            .foregroundColor(.watercolorSlate.opacity(0.6))
                    }
                    .padding(.bottom, 20)

                    if viewModel.substackSuggestions.isEmpty && viewModel.podcastSuggestions.isEmpty && viewModel.subredditSuggestions.isEmpty {
                        Text("No matches found — we'll start you with defaults.")
                            .font(.callout)
                            .foregroundColor(.watercolorSlate.opacity(0.6))
                            .padding(.vertical, 20)
                    }

                    twitterUsernameCard
                        .padding(.bottom, 12)

                    if !viewModel.substackSuggestions.isEmpty {
                        suggestionSection(
                            title: "NEWSLETTERS",
                            icon: "envelope.open",
                            items: viewModel.substackSuggestions,
                            isSelected: { viewModel.selectedSourceKeys.contains($0.feedURL ?? "") },
                            onToggle: { viewModel.toggleSource($0) }
                        )
                    }

                    if !viewModel.podcastSuggestions.isEmpty {
                        suggestionSection(
                            title: "PODCASTS",
                            icon: "headphones",
                            items: viewModel.podcastSuggestions,
                            isSelected: { viewModel.selectedSourceKeys.contains($0.feedURL ?? "") },
                            onToggle: { viewModel.toggleSource($0) }
                        )
                    }

                    if !viewModel.subredditSuggestions.isEmpty {
                        suggestionSection(
                            title: "REDDIT",
                            icon: "bubble.left.and.text.bubble.right",
                            items: viewModel.subredditSuggestions,
                            isSelected: { viewModel.selectedSubreddits.contains($0.subreddit ?? "") },
                            onToggle: { viewModel.toggleSubreddit($0) }
                        )
                    }
                }
                .padding(.horizontal, 24)
                .padding(.top, 24)
                .padding(.bottom, 100)
            }

            // Sticky bottom button
            VStack(spacing: 8) {
                primaryButton("Start reading") {
                    Task { await viewModel.completeOnboarding() }
                }
                .disabled(viewModel.isLoading)

                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                }
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 16)
            .glassCard(cornerRadius: 0)
        }
    }

    private func suggestionSection(
        title: String,
        icon: String,
        items: [OnboardingSuggestion],
        isSelected: @escaping (OnboardingSuggestion) -> Bool,
        onToggle: @escaping (OnboardingSuggestion) -> Void
    ) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(.watercolorSlate.opacity(0.5))
                Text(title)
                    .font(.editorialMeta)
                    .foregroundColor(.watercolorSlate.opacity(0.5))
                    .tracking(1.5)
            }
            .padding(.top, 16)
            .padding(.bottom, 4)

            VStack(spacing: 8) {
                ForEach(Array(items.enumerated()), id: \.element.stableKey) { _, suggestion in
                    SuggestionCard(
                        suggestion: suggestion,
                        isSelected: isSelected(suggestion),
                        onToggle: { onToggle(suggestion) }
                    )
                }
            }
        }
    }

    // MARK: - Shared Components

    private func primaryButton(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.callout.weight(.semibold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .foregroundColor(.white)
                .background(Color.watercolorSlate)
                .clipShape(RoundedRectangle(cornerRadius: 24))
        }
        .buttonStyle(.plain)
    }

    private var twitterUsernameCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("X USERNAME (OPTIONAL)")
                .font(.system(size: 9, weight: .medium))
                .tracking(1.5)
                .foregroundColor(.watercolorSlate.opacity(0.5))

            TextField("@username", text: $viewModel.twitterUsername)
                .textInputAutocapitalization(.never)
                .disableAutocorrection(true)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Color.white.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }
}

// MARK: - Suggestion Card

private struct SuggestionCard: View {
    let suggestion: OnboardingSuggestion
    let isSelected: Bool
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            VStack(alignment: .leading, spacing: 8) {
                // Metadata bar
                HStack(spacing: 6) {
                    Image(systemName: typeIcon)
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(typeAccentColor)

                    Text(sourceLabel.uppercased())
                        .font(.editorialMeta)
                        .foregroundColor(.editorialSub)
                        .tracking(0.5)
                        .lineLimit(1)

                    Spacer()

                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.body)
                        .foregroundColor(isSelected ? .watercolorSlate : Color(.tertiaryLabel))
                }

                // Headline
                Text(suggestion.displayTitle)
                    .font(.editorialHeadline)
                    .foregroundColor(.watercolorSlate)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)

                // Rationale
                if let rationale = suggestion.rationale, !rationale.isEmpty {
                    Text(rationale)
                        .font(.caption)
                        .foregroundColor(.watercolorSlate.opacity(0.6))
                        .lineLimit(2)
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white.opacity(isSelected ? 0.6 : 0.35))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.editorialBorder, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(EditorialCardButtonStyle())
    }

    private var typeIcon: String {
        switch suggestion.suggestionType {
        case "substack", "newsletter": return "envelope.open"
        case "podcast_rss", "podcast": return "waveform"
        case "reddit": return "bubble.left.and.text.bubble.right"
        default: return "doc.text"
        }
    }

    private var typeAccentColor: Color {
        switch suggestion.suggestionType {
        case "substack", "newsletter": return .blue
        case "podcast_rss", "podcast": return .orange
        case "reddit": return .purple
        default: return .blue
        }
    }

    private var sourceLabel: String {
        switch suggestion.suggestionType {
        case "substack", "newsletter": return "Newsletter"
        case "podcast_rss", "podcast": return "Podcast"
        case "reddit": return "Reddit"
        default: return "Feed"
        }
    }
}

// MARK: - Lane Status Row

private struct LaneStatusRow: View {
    let lane: OnboardingDiscoveryLaneStatus

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(statusColor.opacity(0.12))
                    .frame(width: 32, height: 32)
                Image(systemName: statusIcon)
                    .font(.caption.weight(.semibold))
                    .foregroundColor(statusColor)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(lane.name)
                    .font(.callout)
                    .foregroundColor(.watercolorSlate)
                Text(statusLabel)
                    .font(.caption)
                    .foregroundColor(.watercolorSlate.opacity(0.6))
            }
            Spacer()
        }
        .padding(.vertical, 4)
    }

    private var statusLabel: String {
        switch lane.status {
        case "processing": return "Searching..."
        case "completed": return "Done"
        case "failed": return "Failed"
        default: return "Queued"
        }
    }

    private var statusIcon: String {
        switch lane.status {
        case "processing": return "hourglass"
        case "completed": return "checkmark"
        case "failed": return "exclamationmark"
        default: return "circle"
        }
    }

    private var statusColor: Color {
        switch lane.status {
        case "processing": return .watercolorSlate
        case "completed": return .watercolorPaleEmerald
        case "failed": return .watercolorDiffusedPeach
        default: return .watercolorSlate.opacity(0.4)
        }
    }
}

// MARK: - Loading Overlay

private struct LoadingOverlay: View {
    let message: String

    var body: some View {
        VStack(spacing: 10) {
            ProgressView()
                .tint(.watercolorSlate)
            Text(message)
                .font(.callout)
                .foregroundColor(.watercolorSlate.opacity(0.6))
        }
        .padding(20)
        .glassCard(cornerRadius: 14)
        .shadow(color: .black.opacity(0.08), radius: 8, x: 0, y: 4)
    }
}
