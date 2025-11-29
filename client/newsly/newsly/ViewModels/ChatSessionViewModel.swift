//
//  ChatSessionViewModel.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import Foundation
import SwiftUI
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "ChatSessionViewModel")

@MainActor
class ChatSessionViewModel: ObservableObject {
    @Published var session: ChatSessionSummary?
    @Published var messages: [ChatMessage] = []
    @Published var isLoading = false
    @Published var isSending = false
    @Published var errorMessage: String?
    @Published var inputText: String = ""

    // Streaming state
    @Published var streamingMessage: ChatMessage?

    // Voice dictation state
    @Published var isRecording = false
    @Published var isTranscribing = false
    @Published private(set) var voiceDictationAvailable = false

    private let chatService = ChatService.shared
    private let dictationService = VoiceDictationService.shared
    private var streamTask: Task<Void, Never>?

    let sessionId: Int

    init(sessionId: Int) {
        self.sessionId = sessionId
    }

    init(session: ChatSessionSummary) {
        self.sessionId = session.id
        self.session = session
    }

    func loadSession() async {
        logger.debug("[ViewModel] loadSession | sessionId=\(self.sessionId)")
        isLoading = true
        errorMessage = nil

        do {
            let detail = try await chatService.getSession(id: sessionId)
            session = detail.session
            messages = detail.messages

            // If this is an article-based session with no messages, load initial suggestions
            if detail.session.contentId != nil && detail.messages.isEmpty {
                await loadInitialSuggestions()
            }
        } catch {
            errorMessage = error.localizedDescription
            logger.error("[ViewModel] loadSession failed | error=\(error.localizedDescription)")
        }

        isLoading = false
    }

    /// Load initial follow-up question suggestions for article-based sessions
    private func loadInitialSuggestions() async {
        isSending = true

        streamTask = Task {
            do {
                for try await message in chatService.getInitialSuggestions(sessionId: sessionId) {
                    if Task.isCancelled { break }

                    if message.role == .assistant {
                        streamingMessage = message
                    }
                }

                // When stream completes, move streaming message to history
                if let final = streamingMessage {
                    messages.append(final)
                    streamingMessage = nil
                }
            } catch {
                if !Task.isCancelled {
                    logger.error("[ViewModel] loadInitialSuggestions error | error=\(error.localizedDescription)")
                }
            }

            isSending = false
        }
    }

    func sendMessage(text overrideText: String? = nil) async {
        let resolvedText = (overrideText ?? inputText).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !resolvedText.isEmpty, !isSending else { return }

        if overrideText == nil {
            inputText = ""
        }
        isSending = true
        errorMessage = nil

        // Cancel any existing stream
        streamTask?.cancel()

        streamTask = Task {
            do {
                for try await message in chatService.sendMessage(
                    sessionId: sessionId,
                    message: resolvedText
                ) {
                    if Task.isCancelled { break }

                    if message.role == .user {
                        messages.append(message)
                    } else if message.role == .assistant {
                        streamingMessage = message
                    }
                }

                // When stream completes, move streaming message to history
                if let final = streamingMessage {
                    messages.append(final)
                    streamingMessage = nil
                }
            } catch {
                if !Task.isCancelled {
                    errorMessage = error.localizedDescription
                    logger.error("[ViewModel] sendMessage error | error=\(error.localizedDescription)")
                }
            }

            isSending = false
        }
    }

    /// Request counterbalancing arguments via web search.
    func sendCounterArgumentsPrompt() async {
        let subject = counterArgumentSubject()
        let prompt = """
Find counterbalancing arguments online for \(subject). Use the exa_web_search tool to gather opposing viewpoints, cite sources with markdown links, and compare perspectives to the current article/topic.
"""
        await sendMessage(text: prompt)
    }

    private func counterArgumentSubject() -> String {
        if let topic = session?.topic, !topic.isEmpty {
            return "\"\(topic)\""
        }
        if let articleTitle = session?.articleTitle, !articleTitle.isEmpty {
            return "the article \"\(articleTitle)\""
        }
        if let title = session?.title, !title.isEmpty {
            return "\"\(title)\""
        }
        return "this topic"
    }

    func cancelStreaming() {
        streamTask?.cancel()
        streamTask = nil
        streamingMessage = nil
        isSending = false
    }

    /// All messages including any streaming message
    var allMessages: [ChatMessage] {
        if let streaming = streamingMessage {
            return messages + [streaming]
        }
        return messages
    }

    // MARK: - Voice Dictation

    /// Check voice dictation availability and attempt token refresh if key is missing.
    func checkAndRefreshVoiceDictation() async {
        // First check - maybe key is already available
        if isVoiceDictationAvailable {
            voiceDictationAvailable = true
            return
        }

        // Key is missing - try a token refresh to get it from the server
        do {
            _ = try await AuthenticationService.shared.refreshAccessToken()
            voiceDictationAvailable = isVoiceDictationAvailable
        } catch {
            logger.debug("Token refresh for voice dictation failed: \(error.localizedDescription)")
            voiceDictationAvailable = false
        }
    }

    /// Start voice recording for chat message.
    func startVoiceRecording() async {
        do {
            try await dictationService.startRecording()
            isRecording = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Stop recording, transcribe, and auto-send message.
    func stopVoiceRecording() async {
        guard isRecording else { return }

        isRecording = false
        isTranscribing = true

        do {
            let transcription = try await dictationService.stopRecordingAndTranscribe()
            isTranscribing = false

            // Set input text and auto-send
            inputText = transcription
            await sendMessage()
        } catch {
            errorMessage = error.localizedDescription
            isTranscribing = false
        }
    }

    /// Cancel voice recording.
    func cancelVoiceRecording() {
        dictationService.cancelRecording()
        isRecording = false
    }

    /// Check if voice dictation is available.
    private var isVoiceDictationAvailable: Bool {
        // Check Keychain (received from server during auth)
        if let key = KeychainManager.shared.getToken(key: .openaiApiKey),
           !key.isEmpty {
            return true
        }

        // Check Info.plist (fallback for development)
        if let key = Bundle.main.object(forInfoDictionaryKey: "OPENAI_API_KEY") as? String,
           !key.isEmpty, !key.hasPrefix("$(") {
            return true
        }

        // Check environment variable (fallback for development)
        if let key = ProcessInfo.processInfo.environment["OPENAI_API_KEY"],
           !key.isEmpty {
            return true
        }

        return false
    }
}
