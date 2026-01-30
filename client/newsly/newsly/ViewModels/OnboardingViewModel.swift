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
    case profile
    case suggestions
    case subreddits
    case done
}

enum OnboardingSpeechState: Equatable {
    case idle
    case recording
    case processing
    case review
    case error
}

@MainActor
final class OnboardingViewModel: ObservableObject {
    @Published var step: OnboardingStep = .intro
    @Published var firstName: String = ""
    @Published var interestTopicsText: String = ""
    @Published var profileSummary: String?
    @Published var inferredTopics: [String] = []
    @Published var suggestions: OnboardingFastDiscoverResponse?
    @Published var selectedSourceKeys: Set<String> = []
    @Published var selectedSubreddits: Set<String> = []
    @Published var manualSubreddits: [String] = []
    @Published var customSubredditInput: String = ""
    @Published var isLoading = false
    @Published var loadingMessage = ""
    @Published var errorMessage: String?
    @Published var completionResponse: OnboardingCompleteResponse?
    @Published var isPersonalized = false
    @Published var speechState: OnboardingSpeechState = .idle
    @Published var speechTranscript: String = ""
    @Published var speechDurationSeconds: Int = 0
    @Published var isUsingTextFallback = false

    private let service = OnboardingService.shared
    private let transcriptionService = RealtimeTranscriptionService()
    private let user: User
    private var speechTimer: Timer?

    init(user: User) {
        self.user = user
        if let fullName = user.fullName?.split(separator: " ").first {
            firstName = String(fullName)
        }
        configureTranscriptionCallbacks()
    }

    var canSubmitProfile: Bool {
        guard !firstName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return false }
        return !normalizedInterestTopics.isEmpty
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
        step = .subreddits
    }

    func startPersonalized() {
        isPersonalized = true
        step = .profile
        resetSpeechCapture()
    }

    func buildProfileAndDiscover() async {
        guard canSubmitProfile else {
            errorMessage = "Add a first name and at least one topic."
            return
        }

        errorMessage = nil
        isLoading = true
        loadingMessage = "Building your profile"
        defer { isLoading = false }

        do {
            let request = OnboardingProfileRequest(
                firstName: firstName.trimmingCharacters(in: .whitespacesAndNewlines),
                interestTopics: normalizedInterestTopics
            )
            let profile = try await service.buildProfile(request: request)
            profileSummary = profile.profileSummary
            inferredTopics = profile.inferredTopics

            loadingMessage = "Finding podcasts and newsletters"
            let discoverRequest = OnboardingFastDiscoverRequest(
                profileSummary: profile.profileSummary,
                inferredTopics: profile.inferredTopics
            )
            let response = try await service.fastDiscover(request: discoverRequest)
            applySuggestions(response)
            step = .suggestions
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func proceedToSubreddits() {
        step = .subreddits
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

    func addCustomSubreddit() {
        let cleaned = customSubredditInput
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "r/", with: "", options: .caseInsensitive)
            .replacingOccurrences(of: "/r/", with: "", options: .caseInsensitive)
            .replacingOccurrences(of: "/", with: "")

        guard !cleaned.isEmpty else { return }
        if !manualSubreddits.contains(cleaned) {
            manualSubreddits.append(cleaned)
        }
        selectedSubreddits.insert(cleaned)
        customSubredditInput = ""
    }

    func removeManualSubreddit(_ name: String) {
        manualSubreddits.removeAll { $0 == name }
        selectedSubreddits.remove(name)
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
                profileSummary: isPersonalized ? profileSummary : nil,
                inferredTopics: isPersonalized ? inferredTopics : nil
            )
            let response = try await service.complete(request: request)
            completionResponse = response
            step = .done
        } catch {
            errorMessage = error.localizedDescription
        }
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

    private func applySuggestions(_ response: OnboardingFastDiscoverResponse) {
        suggestions = response
        let sourceKeys = (response.recommendedSubstacks + response.recommendedPods)
            .compactMap { $0.feedURL }
        selectedSourceKeys = Set(sourceKeys)
        let subredditKeys = response.recommendedSubreddits.compactMap { $0.subreddit }
        selectedSubreddits = Set(subredditKeys)
    }

    private var normalizedInterestTopics: [String] {
        let rawPieces = interestTopicsText
            .split(whereSeparator: { $0 == "," || $0 == "\n" })
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        var seen: Set<String> = []
        var cleaned: [String] = []
        for topic in rawPieces {
            let normalized = topic.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !normalized.isEmpty else { continue }
            let key = normalized.lowercased()
            guard !seen.contains(key) else { continue }
            seen.insert(key)
            cleaned.append(normalized)
        }
        return cleaned
    }

    func startSpeechCapture() async {
        errorMessage = nil
        speechTranscript = ""
        speechState = .recording
        isUsingTextFallback = false
        startSpeechTimer()

        do {
            try await transcriptionService.start()
        } catch {
            handleSpeechError(error)
        }
    }

    func stopSpeechCaptureAndParse() async {
        speechState = .processing
        stopSpeechTimer()
        let transcript = await transcriptionService.stop()
        await parseTranscript(transcript)
    }

    func useTextFallback() {
        isUsingTextFallback = true
        speechState = .review
        stopSpeechTimer()
    }

    func resetSpeechCapture() {
        transcriptionService.reset()
        speechTranscript = ""
        speechState = .idle
        speechDurationSeconds = 0
        isUsingTextFallback = false
    }

    private func parseTranscript(_ transcript: String) async {
        let cleanedTranscript = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanedTranscript.isEmpty else {
            errorMessage = "We didn’t catch that. Try again or use text input."
            speechState = .review
            return
        }

        do {
            let request = OnboardingVoiceParseRequest(
                transcript: cleanedTranscript,
                locale: Locale.current.identifier
            )
            let response = try await service.parseVoice(request: request)
            if let parsedName = response.firstName, !parsedName.isEmpty {
                firstName = parsedName
            }
            if !response.interestTopics.isEmpty {
                interestTopicsText = response.interestTopics.joined(separator: ", ")
            }
            if !response.missingFields.isEmpty {
                errorMessage = "Add your name and at least one topic."
            }
            speechState = .review
        } catch {
            errorMessage = error.localizedDescription
            speechState = .review
        }
    }

    private func configureTranscriptionCallbacks() {
        transcriptionService.onTranscriptDelta = { [weak self] delta in
            Task { @MainActor in
                self?.speechTranscript.append(delta)
            }
        }
        transcriptionService.onTranscriptFinal = { [weak self] transcript in
            Task { @MainActor in
                self?.speechTranscript = transcript
            }
        }
        transcriptionService.onError = { [weak self] message in
            Task { @MainActor in
                self?.errorMessage = message
                self?.speechState = .error
                self?.stopSpeechTimer()
            }
        }
    }

    private func handleSpeechError(_ error: Error) {
        errorMessage = error.localizedDescription
        speechState = .review
        isUsingTextFallback = true
        stopSpeechTimer()
    }

    private func startSpeechTimer() {
        speechTimer?.invalidate()
        speechDurationSeconds = 0
        speechTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            self?.speechDurationSeconds += 1
        }
    }

    private func stopSpeechTimer() {
        speechTimer?.invalidate()
        speechTimer = nil
    }
}
}
