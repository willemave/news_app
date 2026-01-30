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
    }

    @ViewBuilder
    private var content: some View {
        switch viewModel.step {
        case .intro:
            introView
        case .choice:
            choiceView
        case .profile:
            profileView
        case .suggestions:
            suggestionsView
        case .subreddits:
            subredditsView
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
            Text("We can personalize your subscriptions using your name and a social handle, or you can start with defaults.")
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

    private var profileView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Tell us what you read")
                    .font(.title.bold())
                Text("Speak your name and the kinds of news you want. We’ll build your feed from that.")
                    .foregroundColor(.secondary)

                if viewModel.isUsingTextFallback {
                    profileFieldsView
                } else {
                    switch viewModel.speechState {
                    case .idle:
                        speechIntroCard
                    case .recording:
                        speechRecordingView
                    case .processing:
                        speechProcessingView
                    case .review, .error:
                        profileFieldsView
                    }
                }

                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.footnote)
                        .foregroundColor(.red)
                }
            }
            .padding(32)
        }
    }

    private var profileFieldsView: some View {
        VStack(alignment: .leading, spacing: 12) {
            TextField("First name", text: $viewModel.firstName)
                .textFieldStyle(.roundedBorder)

            TextField("Interest topics (comma-separated)", text: $viewModel.interestTopicsText, axis: .vertical)
                .textFieldStyle(.roundedBorder)

            Text("Add at least one topic to personalize.")
                .font(.footnote)
                .foregroundColor(.secondary)

            Button("Find sources") {
                Task { await viewModel.buildProfileAndDiscover() }
            }
            .buttonStyle(.borderedProminent)
            .disabled(!viewModel.canSubmitProfile || viewModel.isLoading)

            HStack(spacing: 12) {
                Button("Record again") {
                    viewModel.resetSpeechCapture()
                    Task { await viewModel.startSpeechCapture() }
                }
                .buttonStyle(.bordered)

                Button("Use defaults instead") {
                    viewModel.chooseDefaults()
                }
                .buttonStyle(.bordered)
            }
        }
    }

    private var speechIntroCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: "mic.fill")
                    .font(.system(size: 28, weight: .semibold))
                    .foregroundColor(.blue)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Tell us about yourself")
                        .font(.headline)
                    Text("Say your name and what kinds of news you want.")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                Spacer()
            }

            Button("Start recording") {
                Task { await viewModel.startSpeechCapture() }
            }
            .buttonStyle(.borderedProminent)

            Button("Use text input") {
                viewModel.useTextFallback()
            }
            .buttonStyle(.bordered)

            Button("Use defaults instead") {
                viewModel.chooseDefaults()
            }
            .buttonStyle(.bordered)
        }
        .padding(16)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var speechRecordingView: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "waveform")
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundColor(.red)
                Text("Listening • \(formattedSpeechDuration)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Spacer()
            }

            TextEditor(text: $viewModel.speechTranscript)
                .frame(minHeight: 120)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.secondary.opacity(0.4)))

            Text("You can edit the transcript while you speak.")
                .font(.footnote)
                .foregroundColor(.secondary)

            Button("Stop and use this") {
                Task { await viewModel.stopSpeechCaptureAndParse() }
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private var speechProcessingView: some View {
        HStack(spacing: 12) {
            ProgressView()
            Text("Turning that into your profile...")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding(12)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var formattedSpeechDuration: String {
        let minutes = viewModel.speechDurationSeconds / 60
        let seconds = viewModel.speechDurationSeconds % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    private var suggestionsView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Top picks for you")
                    .font(.title.bold())
                Text("Review the suggested Substacks, feeds, and podcasts. You can edit these later.")
                    .foregroundColor(.secondary)

                if viewModel.substackSuggestions.isEmpty && viewModel.podcastSuggestions.isEmpty {
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

                Button("Continue") {
                    viewModel.proceedToSubreddits()
                }
                .buttonStyle(.borderedProminent)

                Button("Skip this step") {
                    viewModel.proceedToSubreddits()
                }
                .buttonStyle(.bordered)

                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.footnote)
                        .foregroundColor(.red)
                }
            }
            .padding(32)
        }
    }

    private var subredditsView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Add subreddits (optional)")
                    .font(.title.bold())
                Text("Follow discussions you care about. Add `r/` or just the subreddit name.")
                    .foregroundColor(.secondary)

                if !viewModel.subredditSuggestions.isEmpty {
                    sectionHeader("Suggested")
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

                HStack {
                    TextField("e.g. MachineLearning", text: $viewModel.customSubredditInput)
                        .textFieldStyle(.roundedBorder)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .onSubmit {
                            viewModel.addCustomSubreddit()
                        }
                    Button("Add") {
                        viewModel.addCustomSubreddit()
                    }
                    .buttonStyle(.bordered)
                }

                if !viewModel.manualSubreddits.isEmpty {
                    sectionHeader("Custom")
                    ForEach(viewModel.manualSubreddits, id: \.self) { subreddit in
                        HStack {
                            Text("r/\(subreddit)")
                                .font(.body)
                            Spacer()
                            Button {
                                viewModel.removeManualSubreddit(subreddit)
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding(.vertical, 6)
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
