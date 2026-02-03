//
//  OnboardingViewModel.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import Foundation

enum OnboardingStep: Int {
    case intro
    case choice
    case audio
    case loading
    case suggestions
    case done
}

enum OnboardingAudioState: Equatable {
    case idle
    case recording
    case transcribing
    case error
}

@MainActor
final class OnboardingViewModel: ObservableObject {
    @Published var step: OnboardingStep = .intro
    @Published var suggestions: OnboardingFastDiscoverResponse?
    @Published var selectedSourceKeys: Set<String> = []
    @Published var selectedSubreddits: Set<String> = []
    @Published var isLoading = false
    @Published var loadingMessage = ""
    @Published var errorMessage: String?
    @Published var completionResponse: OnboardingCompleteResponse?
    @Published var isPersonalized = false

    @Published var audioState: OnboardingAudioState = .idle
    @Published var audioDurationSeconds: Int = 0
    @Published var hasMicPermissionDenied = false
    @Published var hasDictationError = false

    @Published var discoveryLanes: [OnboardingDiscoveryLaneStatus] = []
    @Published var discoveryRunId: Int?
    @Published var discoveryRunStatus: String?
    @Published var discoveryErrorMessage: String?
    @Published var topicSummary: String?
    @Published var inferredTopics: [String] = []

    private let service = OnboardingService.shared
    private let dictationService = VoiceDictationService.shared
    private let onboardingStateStore = OnboardingStateStore.shared
    private let user: User
    private var audioTimer: Timer?
    private var pollingTask: Task<Void, Never>?
    private var didAutoStartRecording = false
    private var didAttemptResume = false

    init(user: User) {
        self.user = user
    }

    deinit {
        pollingTask?.cancel()
        audioTimer?.invalidate()
    }

    var substackSuggestions: [OnboardingSuggestion] {
        suggestions?.recommendedSubstacks ?? []
    }

    var podcastSuggestions: [OnboardingSuggestion] {
        suggestions?.recommendedPods ?? []
    }

    var subredditSuggestions: [OnboardingSuggestion] {
        suggestions?.recommendedSubreddits ?? []
    }

    func advanceToChoice() {
        step = .choice
    }

    func chooseDefaults() {
        isPersonalized = false
        stopAudioCapture()
        clearDiscoveryState()
        Task { await completeOnboarding() }
    }

    func startPersonalized() {
        isPersonalized = true
        step = .audio
        resetAudioState()
    }

    func resumeDiscoveryIfNeeded() async {
        guard !didAttemptResume else { return }
        didAttemptResume = true

        guard let runId = onboardingStateStore.discoveryRunId(userId: user.id) else { return }
        discoveryRunId = runId
        step = .loading
        await refreshDiscoveryStatus(runId: runId)
        startPolling(runId: runId)
    }

    func startAudioCaptureIfNeeded() async {
        guard !didAutoStartRecording else { return }
        didAutoStartRecording = true
        await startAudioCapture()
    }

    func startAudioCapture() async {
        errorMessage = nil
        hasMicPermissionDenied = false
        hasDictationError = false
        audioState = .recording
        startAudioTimer()

        do {
            try await dictationService.start()
        } catch {
            handleAudioError(error)
        }
    }

    func stopAudioCaptureAndDiscover() async {
        audioState = .transcribing
        stopAudioTimer()
        do {
            let transcript = try await dictationService.stop()
            await beginDiscovery(transcript: transcript)
        } catch {
            handleAudioError(error)
        }
    }

    func resetAudioState() {
        dictationService.cancel()
        audioState = .idle
        audioDurationSeconds = 0
        hasMicPermissionDenied = false
        hasDictationError = false
        errorMessage = nil
        didAutoStartRecording = false
        stopAudioTimer()
    }

    func toggleSource(_ suggestion: OnboardingSuggestion) {
        guard let feedURL = suggestion.feedURL, !feedURL.isEmpty else { return }
        if selectedSourceKeys.contains(feedURL) {
            selectedSourceKeys.remove(feedURL)
        } else {
            selectedSourceKeys.insert(feedURL)
        }
    }

    func toggleSubreddit(_ suggestion: OnboardingSuggestion) {
        guard let subreddit = suggestion.subreddit, !subreddit.isEmpty else { return }
        if selectedSubreddits.contains(subreddit) {
            selectedSubreddits.remove(subreddit)
        } else {
            selectedSubreddits.insert(subreddit)
        }
    }

    func completeOnboarding() async {
        errorMessage = nil
        isLoading = true
        loadingMessage = "Setting up your inbox"
        defer { isLoading = false }

        do {
            let selectedSources = buildSelectedSources()
            let selectedSubreddits = Array(self.selectedSubreddits)
            let request = OnboardingCompleteRequest(
                selectedSources: selectedSources,
                selectedSubreddits: selectedSubreddits,
                profileSummary: isPersonalized ? topicSummary : nil,
                inferredTopics: isPersonalized ? inferredTopics : nil
            )
            let response = try await service.complete(request: request)
            completionResponse = response
            onboardingStateStore.clearDiscoveryRun(userId: user.id)
            step = .done
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func beginDiscovery(transcript: String) async {
        do {
            let request = OnboardingAudioDiscoverRequest(
                transcript: transcript,
                locale: Locale.current.identifier
            )
            let response = try await service.audioDiscover(request: request)
            discoveryRunId = response.runId
            discoveryRunStatus = response.runStatus
            topicSummary = response.topicSummary
            inferredTopics = response.inferredTopics
            discoveryLanes = response.lanes
            onboardingStateStore.setDiscoveryRun(userId: user.id, runId: response.runId)
            step = .loading
            startPolling(runId: response.runId)
        } catch {
            errorMessage = error.localizedDescription
            audioState = .error
            hasDictationError = true
        }
    }

    private func refreshDiscoveryStatus(runId: Int) async {
        do {
            let status = try await service.discoveryStatus(runId: runId)
            applyDiscoveryStatus(status)
        } catch {
            discoveryErrorMessage = error.localizedDescription
        }
    }

    private func startPolling(runId: Int) {
        pollingTask?.cancel()
        pollingTask = Task { @MainActor in
            let deadline = Date().addingTimeInterval(60)
            while !Task.isCancelled {
                await refreshDiscoveryStatus(runId: runId)

                if let status = discoveryRunStatus, status == "completed" || status == "failed" {
                    break
                }

                if Date() >= deadline {
                    handleDiscoveryTimeout()
                    break
                }

                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
    }

    private func applyDiscoveryStatus(_ status: OnboardingDiscoveryStatusResponse) {
        discoveryRunId = status.runId
        discoveryRunStatus = status.runStatus
        discoveryLanes = status.lanes
        topicSummary = status.topicSummary
        inferredTopics = status.inferredTopics
        discoveryErrorMessage = status.errorMessage

        if status.runStatus == "completed" {
            if let suggestions = status.suggestions {
                applySuggestions(suggestions)
            }
            errorMessage = nil
            step = .suggestions
        } else if status.runStatus == "failed" {
            suggestions = nil
            errorMessage = status.errorMessage ?? "Discovery failed. We'll start you with defaults."
            step = .suggestions
            onboardingStateStore.clearDiscoveryRun(userId: user.id)
        }
    }

    private func applySuggestions(_ response: OnboardingFastDiscoverResponse) {
        suggestions = response
        let sourceKeys = (response.recommendedSubstacks + response.recommendedPods)
            .compactMap { $0.feedURL }
        selectedSourceKeys = Set(sourceKeys)
        let subredditKeys = response.recommendedSubreddits.compactMap { $0.subreddit }
        selectedSubreddits = Set(subredditKeys)
    }

    private func buildSelectedSources() -> [OnboardingSelectedSource] {
        let combined = substackSuggestions + podcastSuggestions
        return combined.compactMap { suggestion in
            guard let feedURL = suggestion.feedURL, selectedSourceKeys.contains(feedURL) else { return nil }
            return OnboardingSelectedSource(
                suggestionType: suggestion.suggestionType,
                title: suggestion.title,
                feedURL: feedURL,
                config: nil
            )
        }
    }

    private func handleAudioError(_ error: Error) {
        errorMessage = error.localizedDescription
        if let dictationError = error as? VoiceDictationError {
            switch dictationError {
            case .noMicrophoneAccess:
                hasMicPermissionDenied = true
                audioState = .error
            default:
                hasDictationError = true
                audioState = .error
            }
        } else {
            hasDictationError = true
            audioState = .error
        }
        stopAudioTimer()
    }

    private func handleDiscoveryTimeout() {
        discoveryErrorMessage = "Discovery is taking longer than expected."
        suggestions = nil
        errorMessage = "Discovery is taking longer than expected. We'll start you with defaults."
        onboardingStateStore.clearDiscoveryRun(userId: user.id)
        step = .suggestions
    }

    private func clearDiscoveryState() {
        pollingTask?.cancel()
        discoveryRunId = nil
        discoveryRunStatus = nil
        discoveryLanes = []
        discoveryErrorMessage = nil
        topicSummary = nil
        inferredTopics = []
        suggestions = nil
        selectedSourceKeys = []
        selectedSubreddits = []
        onboardingStateStore.clearDiscoveryRun(userId: user.id)
    }

    private func stopAudioCapture() {
        dictationService.cancel()
        stopAudioTimer()
        audioState = .idle
    }

    private func startAudioTimer() {
        audioTimer?.invalidate()
        audioDurationSeconds = 0
        audioTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.audioDurationSeconds += 1
            if self.audioDurationSeconds >= 30 && self.audioState == .recording {
                Task { await self.stopAudioCaptureAndDiscover() }
            }
        }
    }

    private func stopAudioTimer() {
        audioTimer?.invalidate()
        audioTimer = nil
    }
}
