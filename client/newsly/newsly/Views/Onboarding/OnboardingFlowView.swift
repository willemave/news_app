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
                .onChange(of: viewModel.completionResponse) { _, response in
                    if let response {
                        onFinish(response)
                    }
                }
        }
    }

    // MARK: - Intro

    private var introView: some View {
        VStack(spacing: 0) {
            ZStack(alignment: .bottom) {
                AncientScrollRevealView(
                    obfuscatedSeed: 0xA53F_71D2,
                    showsPhysics: true
                ) { _ in }
                .overlay(alignment: .bottom) {
                    LinearGradient(
                        colors: [
                            Color.black.opacity(0.0),
                            Color.black.opacity(0.25)
                        ],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    .frame(height: 100)
                    .allowsHitTesting(false)
                }

                HStack(spacing: 6) {
                    Image(systemName: "hand.draw.fill")
                        .font(.caption2)
                    Text("Swipe to scatter")
                        .font(.caption.weight(.medium))
                }
                .foregroundStyle(.white.opacity(0.55))
                .padding(.bottom, 16)
                .allowsHitTesting(false)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            VStack(spacing: 12) {
                primaryButton("Get started") {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        viewModel.advanceToChoice()
                    }
                }

                Text("Takes about 1 minute")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 24)
            .padding(.top, 14)
            .padding(.bottom, 8)
            .background(
                ZStack {
                    Color(UIColor.systemBackground).opacity(0.9)
                    Rectangle().fill(.thinMaterial)
                }
                .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: -2)
            )
        }
        .ignoresSafeArea(edges: .top)
    }

    // MARK: - Choice

    private var choiceView: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 24) {
                ZStack {
                    Circle()
                        .fill(Color.accentColor.opacity(0.1))
                        .frame(width: 88, height: 88)
                    Image(systemName: "slider.horizontal.3")
                        .font(.system(size: 32, weight: .medium))
                        .foregroundColor(.accentColor)
                }

                VStack(spacing: 10) {
                    Text("Set up your feeds")
                        .font(.title2.bold())
                    Text("Share what you read and we'll\ncurate the best sources for you.")
                        .font(.callout)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
            }

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
                    .foregroundColor(isPrimary ? .white : .accentColor)
                    .frame(width: 36, height: 36)
                    .background(isPrimary ? Color.accentColor : Color.accentColor.opacity(0.12))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.callout.weight(.semibold))
                        .foregroundColor(.primary)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.secondary)
            }
            .padding(16)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Audio

    private var audioView: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Tell us what you read")
                    .font(.title2.bold())
                Text("Speak naturally about your interests.")
                    .font(.callout)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 24)

            Spacer()

            switch viewModel.audioState {
            case .idle:
                audioIdleView
            case .recording:
                audioActiveView
            case .transcribing:
                audioProcessingView
            case .error:
                audioErrorView
            }

            Spacer()

            if viewModel.audioState != .transcribing {
                Button("Use defaults instead") {
                    viewModel.chooseDefaults()
                }
                .font(.callout)
                .foregroundColor(.secondary)
                .padding(.bottom, 8)
            }

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.bottom, 4)
            }
        }
        .padding(.horizontal, 24)
        .task {
            await viewModel.startAudioCaptureIfNeeded()
        }
    }

    private var audioIdleView: some View {
        VStack(spacing: 20) {
            ZStack {
                Circle()
                    .fill(Color.accentColor.opacity(0.1))
                    .frame(width: 100, height: 100)
                Image(systemName: "mic.fill")
                    .font(.system(size: 36, weight: .medium))
                    .foregroundColor(.accentColor)
            }

            Text("Tap to start recording")
                .font(.callout)
                .foregroundColor(.secondary)

            primaryButton("Start recording") {
                Task { await viewModel.startAudioCapture() }
            }
            .frame(maxWidth: 240)
        }
    }

    private var audioActiveView: some View {
        VStack(spacing: 20) {
            ZStack {
                // Pulsing ring
                Circle()
                    .stroke(Color.red.opacity(0.2), lineWidth: 3)
                    .frame(width: 100, height: 100)
                Circle()
                    .fill(Color.red.opacity(0.1))
                    .frame(width: 100, height: 100)
                Image(systemName: "waveform")
                    .font(.system(size: 32, weight: .medium))
                    .foregroundColor(.red)
            }

            VStack(spacing: 4) {
                Text("Listening...")
                    .font(.callout.weight(.medium))
                Text(formattedAudioDuration)
                    .font(.title3.monospacedDigit())
                    .foregroundColor(.secondary)
            }

            primaryButton("Done") {
                Task { await viewModel.stopAudioCaptureAndDiscover() }
            }
            .frame(maxWidth: 240)
        }
    }

    private var audioProcessingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.2)
            Text("Processing your interests...")
                .font(.callout)
                .foregroundColor(.secondary)
        }
    }

    private var audioErrorView: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(Color.orange.opacity(0.1))
                    .frame(width: 80, height: 80)
                Image(systemName: "exclamationmark.triangle")
                    .font(.system(size: 28, weight: .medium))
                    .foregroundColor(.orange)
            }

            Text("Recording failed")
                .font(.callout.weight(.medium))

            primaryButton("Try again") {
                Task { await viewModel.startAudioCapture() }
            }
            .frame(maxWidth: 240)
        }
    }

    private var formattedAudioDuration: String {
        let minutes = viewModel.audioDurationSeconds / 60
        let seconds = viewModel.audioDurationSeconds % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    // MARK: - Loading / Discovery

    private var loadingView: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Finding your feeds")
                    .font(.title2.bold())
                Text("Searching newsletters, podcasts, and Reddit.")
                    .font(.callout)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 24)

            Spacer()

            VStack(spacing: 16) {
                if viewModel.discoveryLanes.isEmpty {
                    ProgressView()
                        .scaleEffect(1.2)
                    Text("Preparing search...")
                        .font(.callout)
                        .foregroundColor(.secondary)
                } else {
                    ForEach(viewModel.discoveryLanes) { lane in
                        LaneStatusRow(lane: lane)
                    }
                }
            }

            Spacer()

            VStack(spacing: 12) {
                Text("Usually takes under a minute")
                    .font(.caption)
                    .foregroundColor(.secondary)

                if let message = viewModel.discoveryErrorMessage {
                    Text(message)
                        .font(.caption)
                        .foregroundColor(.orange)
                }

                Button("Use defaults instead") {
                    viewModel.chooseDefaults()
                }
                .font(.callout)
                .foregroundColor(.secondary)
            }
        }
        .padding(24)
    }

    // MARK: - Suggestions

    private var suggestionsView: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Your picks")
                            .font(.title2.bold())
                        Text("Tap to deselect any you don't want.")
                            .font(.callout)
                            .foregroundColor(.secondary)
                    }
                    .padding(.bottom, 20)

                    if viewModel.substackSuggestions.isEmpty && viewModel.podcastSuggestions.isEmpty && viewModel.subredditSuggestions.isEmpty {
                        Text("No matches found — we'll start you with defaults.")
                            .font(.callout)
                            .foregroundColor(.secondary)
                            .padding(.vertical, 20)
                    }

                    if !viewModel.substackSuggestions.isEmpty {
                        suggestionSection(
                            title: "Newsletters",
                            icon: "envelope.open",
                            items: viewModel.substackSuggestions,
                            isSelected: { viewModel.selectedSourceKeys.contains($0.feedURL ?? "") },
                            onToggle: { viewModel.toggleSource($0) }
                        )
                    }

                    if !viewModel.podcastSuggestions.isEmpty {
                        suggestionSection(
                            title: "Podcasts",
                            icon: "headphones",
                            items: viewModel.podcastSuggestions,
                            isSelected: { viewModel.selectedSourceKeys.contains($0.feedURL ?? "") },
                            onToggle: { viewModel.toggleSource($0) }
                        )
                    }

                    if !viewModel.subredditSuggestions.isEmpty {
                        suggestionSection(
                            title: "Reddit",
                            icon: "bubble.left.and.text.bubble.right",
                            items: viewModel.subredditSuggestions,
                            isSelected: { viewModel.selectedSubreddits.contains($0.subreddit ?? "") },
                            onToggle: { viewModel.toggleSubreddit($0) }
                        )
                    }
                }
                .padding(.horizontal, 24)
                .padding(.top, 24)
                .padding(.bottom, 16)
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
            .padding(.bottom, 16)
            .padding(.top, 8)
            .background(
                Color(UIColor.systemBackground)
                    .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: -4)
            )
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
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.secondary)
            }
            .padding(.top, 16)
            .padding(.bottom, 4)

            VStack(spacing: 0) {
                ForEach(Array(items.enumerated()), id: \.element.stableKey) { index, suggestion in
                    SuggestionRow(
                        title: suggestion.displayTitle,
                        subtitle: suggestion.rationale,
                        isSelected: isSelected(suggestion)
                    ) {
                        onToggle(suggestion)
                    }

                    if index < items.count - 1 {
                        Divider()
                            .padding(.leading, 36)
                    }
                }
            }
            .padding(.vertical, 4)
            .padding(.horizontal, 12)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))
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
                .background(Color.accentColor)
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
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
                Text(statusLabel)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
        .padding(.vertical, 8)
    }

    private var statusLabel: String {
        switch lane.status {
        case "processing":
            return "Searching..."
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
            return "checkmark"
        case "failed":
            return "exclamationmark"
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
            HStack(spacing: 10) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.body)
                    .foregroundColor(isSelected ? .accentColor : Color(.tertiaryLabel))

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.callout.weight(.medium))
                        .foregroundColor(isSelected ? .primary : .secondary)
                    if let subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(2)
                    }
                }
                Spacer()
            }
            .padding(.vertical, 10)
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
