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

@MainActor
final class OnboardingViewModel: ObservableObject {
    @Published var step: OnboardingStep = .intro
    @Published var firstName: String = ""
    @Published var twitterHandle: String = ""
    @Published var linkedinHandle: String = ""
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

    private let service = OnboardingService.shared
    private let user: User

    init(user: User) {
        self.user = user
        if let fullName = user.fullName?.split(separator: " ").first {
            firstName = String(fullName)
        }
    }

    var canSubmitProfile: Bool {
        guard !firstName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return false }
        let twitter = twitterHandle.trimmingCharacters(in: .whitespacesAndNewlines)
        let linkedin = linkedinHandle.trimmingCharacters(in: .whitespacesAndNewlines)
        return !twitter.isEmpty || !linkedin.isEmpty
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
    }

    func buildProfileAndDiscover() async {
        guard canSubmitProfile else {
            errorMessage = "Add a first name and at least one handle."
            return
        }

        errorMessage = nil
        isLoading = true
        loadingMessage = "Building your profile"
        defer { isLoading = false }

        do {
            let request = OnboardingProfileRequest(
                firstName: firstName.trimmingCharacters(in: .whitespacesAndNewlines),
                twitterHandle: normalizedHandle(twitterHandle),
                linkedinHandle: normalizedHandle(linkedinHandle)
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

    private func normalizedHandle(_ input: String) -> String? {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        if trimmed.hasPrefix("@") {
            return String(trimmed.dropFirst())
        }
        return trimmed
    }
}
