//
//  TweetSuggestionsViewModel.swift
//  newsly
//
//  ViewModel for tweet suggestions sheet.
//

import Foundation
import os.log
import UIKit

private let logger = Logger(subsystem: "com.newsly", category: "TweetSuggestions")

@MainActor
final class TweetSuggestionsViewModel: ObservableObject {
    // MARK: - Published Properties

    @Published var suggestions: [TweetSuggestion] = []
    @Published var creativity: Int = 5
    @Published var tweakMessage: String = ""
    @Published var isLoading = false
    @Published var isRegenerating = false
    @Published var errorMessage: String?
    @Published var selectedSuggestionId: Int?
    @Published var selectedProvider: ChatModelProvider = .google

    // Voice dictation state
    @Published var isRecording = false
    @Published var isTranscribing = false
    @Published private(set) var voiceDictationAvailable = false

    // MARK: - Private Properties

    private let contentService = ContentService.shared
    private let twitterService = TwitterShareService.shared
    private let transcriptionService: any SpeechTranscribing
    private var contentId: Int?
    private var creativityDebounceTask: Task<Void, Never>?
    private var lastCreativity: Int = 5

    // MARK: - Public Methods

    init(transcriptionService: any SpeechTranscribing = VoiceDictationService.shared) {
        self.transcriptionService = transcriptionService
    }

    /// Initialize with content ID and generate suggestions.
    func initialize(contentId: Int) async {
        self.contentId = contentId
        lastCreativity = creativity

        // Check voice dictation availability, refresh token if needed
        await checkAndRefreshVoiceDictation()

        await generateSuggestions()
    }

    /// Check voice dictation availability and attempt token refresh if key is missing.
    private func checkAndRefreshVoiceDictation() async {
        // First check - maybe key is already available
        if isVoiceDictationAvailable {
            voiceDictationAvailable = true
            return
        }

        // Key is missing - try a token refresh to get it from the server
        // This helps users who authenticated before the feature was added
        logger.info("🎤 OpenAI key missing, attempting token refresh...")

        do {
            _ = try await AuthenticationService.shared.refreshAccessToken()
            // Check again after refresh
            voiceDictationAvailable = isVoiceDictationAvailable
            if voiceDictationAvailable {
                logger.info("🎤 Token refresh provided OpenAI key - voice dictation now available!")
            } else {
                logger.warning("🎤 Token refresh completed but OpenAI key still not available")
            }
        } catch {
            logger.warning("🎤 Token refresh failed: \(error.localizedDescription)")
            voiceDictationAvailable = false
        }
    }

    /// Check and update voice dictation availability (synchronous, for manual refresh).
    func checkVoiceDictationAvailability() {
        voiceDictationAvailable = isVoiceDictationAvailable
    }

    /// Called when creativity slider changes - debounces and auto-regenerates.
    func creativityChanged(to newValue: Int) {
        guard newValue != lastCreativity else { return }

        // Cancel any pending debounce task
        creativityDebounceTask?.cancel()

        // Debounce: wait 500ms after user stops sliding before regenerating
        creativityDebounceTask = Task {
            try? await Task.sleep(nanoseconds: 500_000_000) // 500ms

            guard !Task.isCancelled else { return }

            lastCreativity = newValue
            await regenerate()
        }
    }

    /// Switch to a different LLM provider and regenerate.
    func switchProvider(to provider: ChatModelProvider) async {
        guard provider != selectedProvider else { return }
        selectedProvider = provider
        await regenerate()
    }

    /// Generate tweet suggestions.
    func generateSuggestions() async {
        guard let contentId = contentId else { return }

        isLoading = true
        errorMessage = nil

        do {
            let message = tweakMessage.isEmpty ? nil : tweakMessage
            let response = try await contentService.generateTweetSuggestions(
                id: contentId,
                message: message,
                creativity: creativity,
                provider: selectedProvider
            )
            suggestions = response.suggestions
            logger.info("Generated \(response.suggestions.count) tweet suggestions")
        } catch {
            logger.error("Failed to generate suggestions: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    /// Regenerate suggestions with current settings.
    func regenerate() async {
        isRegenerating = true
        await generateSuggestions()
        isRegenerating = false
    }

    /// Select a suggestion.
    func selectSuggestion(_ suggestion: TweetSuggestion) {
        selectedSuggestionId = suggestion.id
    }

    /// Share selected suggestion to Twitter.
    func shareToTwitter() {
        guard let selectedId = selectedSuggestionId,
              let suggestion = suggestions.first(where: { $0.id == selectedId }) else {
            return
        }

        twitterService.share(tweet: suggestion.text) { success in
            if success {
                logger.info("Successfully shared tweet")
            } else {
                logger.error("Failed to share tweet")
            }
        }
    }

    /// Share a specific suggestion to Twitter.
    func shareToTwitter(suggestion: TweetSuggestion) {
        twitterService.share(tweet: suggestion.text) { success in
            if success {
                logger.info("Successfully shared tweet")
            } else {
                logger.error("Failed to share tweet")
            }
        }
    }

    /// Copy suggestion text to clipboard.
    func copyToClipboard(suggestion: TweetSuggestion) {
        UIPasteboard.general.string = suggestion.text
        logger.info("Copied tweet to clipboard")
    }

    // MARK: - Voice Dictation

    /// Start voice recording for tweak message.
    func startVoiceRecording() async {
        do {
            try await transcriptionService.start()
            isRecording = true
        } catch {
            logger.error("Failed to start recording: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }
    }

    /// Stop recording, transcribe, and auto-regenerate suggestions.
    func stopVoiceRecording() async {
        guard isRecording else { return }

        isRecording = false
        isTranscribing = true

        do {
            let transcription = try await transcriptionService.stop()
            // Append to existing tweak message
            if tweakMessage.isEmpty {
                tweakMessage = transcription
            } else {
                tweakMessage += " " + transcription
            }
            isTranscribing = false

            // Auto-regenerate with the new tweak message
            await regenerate()
        } catch {
            logger.error("Failed to transcribe: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
            isTranscribing = false
        }
    }

    /// Cancel voice recording.
    func cancelVoiceRecording() {
        transcriptionService.cancel()
        isRecording = false
    }

    // MARK: - Helpers

    /// Get the creativity label for display.
    var creativityLabel: String {
        switch creativity {
        case 1...3:
            return "Journalist"
        case 4...7:
            return "Insider"
        case 8...10:
            return "Thought Leader"
        default:
            return "Insider"
        }
    }

    /// Check if voice dictation is available.
    var isVoiceDictationAvailable: Bool {
        logger.debug("🎤 Checking voice dictation availability...")

        // Check Keychain (received from server during auth)
        if let key = KeychainManager.shared.getToken(key: .openaiApiKey),
           !key.isEmpty {
            logger.info("🎤 Voice dictation AVAILABLE via Keychain (length: \(key.count))")
            return true
        } else {
            logger.debug("🎤 No OpenAI key in Keychain")
        }

        // Check Info.plist (fallback for development)
        if let key = Bundle.main.object(forInfoDictionaryKey: "OPENAI_API_KEY") as? String,
           !key.isEmpty, !key.hasPrefix("$(") {
            logger.info("🎤 Voice dictation AVAILABLE via Info.plist (length: \(key.count))")
            return true
        } else {
            let plistValue = Bundle.main.object(forInfoDictionaryKey: "OPENAI_API_KEY") as? String
            logger.debug("🎤 Info.plist OPENAI_API_KEY: \(plistValue ?? "nil")")
        }

        // Check environment variable (fallback for development)
        if let key = ProcessInfo.processInfo.environment["OPENAI_API_KEY"],
           !key.isEmpty {
            logger.info("🎤 Voice dictation AVAILABLE via environment (length: \(key.count))")
            return true
        } else {
            logger.debug("🎤 No OPENAI_API_KEY environment variable")
        }

        logger.warning("🎤 Voice dictation NOT AVAILABLE - no API key found in any source")
        return false
    }
}
