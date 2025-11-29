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
        logger.info("[ViewModel] loadSession started | sessionId=\(self.sessionId)")
        isLoading = true
        errorMessage = nil

        do {
            let detail = try await chatService.getSession(id: sessionId)
            session = detail.session
            messages = detail.messages
            logger.info("[ViewModel] loadSession loaded | sessionId=\(self.sessionId) messageCount=\(detail.messages.count) hasContentId=\(detail.session.contentId != nil)")

            // If this is an article-based session with no messages, load initial suggestions
            if detail.session.contentId != nil && detail.messages.isEmpty {
                logger.info("[ViewModel] loadSession triggering initial suggestions | sessionId=\(self.sessionId)")
                await loadInitialSuggestions()
            }
        } catch {
            errorMessage = error.localizedDescription
            logger.error("[ViewModel] loadSession failed | sessionId=\(self.sessionId) error=\(error.localizedDescription)")
        }

        isLoading = false
        logger.info("[ViewModel] loadSession completed | sessionId=\(self.sessionId)")
    }

    /// Load initial follow-up question suggestions for article-based sessions
    private func loadInitialSuggestions() async {
        logger.info("[ViewModel] loadInitialSuggestions started | sessionId=\(self.sessionId)")
        isSending = true

        streamTask = Task {
            var chunkCount = 0
            do {
                logger.info("[ViewModel] loadInitialSuggestions starting stream iteration | sessionId=\(self.sessionId)")
                for try await message in chatService.getInitialSuggestions(sessionId: sessionId) {
                    if Task.isCancelled {
                        logger.info("[ViewModel] loadInitialSuggestions cancelled | sessionId=\(self.sessionId) chunks=\(chunkCount)")
                        break
                    }

                    chunkCount += 1
                    if message.role == .assistant {
                        streamingMessage = message
                        logger.debug("[ViewModel] loadInitialSuggestions chunk #\(chunkCount) | sessionId=\(self.sessionId) contentLen=\(message.content.count)")
                    }
                }

                logger.info("[ViewModel] loadInitialSuggestions stream ended | sessionId=\(self.sessionId) totalChunks=\(chunkCount)")

                // When stream completes, move streaming message to history
                if let final = streamingMessage {
                    messages.append(final)
                    streamingMessage = nil
                    logger.info("[ViewModel] loadInitialSuggestions finalized | sessionId=\(self.sessionId) finalContentLen=\(final.content.count)")
                } else {
                    logger.warning("[ViewModel] loadInitialSuggestions no final message | sessionId=\(self.sessionId)")
                }
            } catch {
                if !Task.isCancelled {
                    logger.error("[ViewModel] loadInitialSuggestions error | sessionId=\(self.sessionId) error=\(error.localizedDescription)")
                }
            }

            isSending = false
            logger.info("[ViewModel] loadInitialSuggestions completed | sessionId=\(self.sessionId)")
        }
    }

    func sendMessage() async {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else {
            logger.debug("[ViewModel] sendMessage skipped | sessionId=\(self.sessionId) isEmpty=\(text.isEmpty) isSending=\(self.isSending)")
            return
        }

        logger.info("[ViewModel] sendMessage started | sessionId=\(self.sessionId) textLen=\(text.count)")
        inputText = ""
        isSending = true
        errorMessage = nil

        // Cancel any existing stream
        if streamTask != nil {
            logger.info("[ViewModel] sendMessage cancelling existing stream | sessionId=\(self.sessionId)")
            streamTask?.cancel()
        }

        streamTask = Task {
            var chunkCount = 0
            var userMessageReceived = false
            do {
                logger.info("[ViewModel] sendMessage starting stream iteration | sessionId=\(self.sessionId)")
                for try await message in chatService.sendMessage(sessionId: sessionId, message: text) {
                    if Task.isCancelled {
                        logger.info("[ViewModel] sendMessage cancelled | sessionId=\(self.sessionId) chunks=\(chunkCount)")
                        break
                    }

                    chunkCount += 1
                    if message.role == .user {
                        // Add user message to history
                        messages.append(message)
                        userMessageReceived = true
                        logger.debug("[ViewModel] sendMessage user msg received | sessionId=\(self.sessionId)")
                    } else if message.role == .assistant {
                        // Update streaming message (each chunk replaces the previous)
                        streamingMessage = message
                        logger.debug("[ViewModel] sendMessage assistant chunk #\(chunkCount) | sessionId=\(self.sessionId) contentLen=\(message.content.count)")
                    }
                }

                logger.info("[ViewModel] sendMessage stream ended | sessionId=\(self.sessionId) totalChunks=\(chunkCount) userMsgReceived=\(userMessageReceived)")

                // When stream completes, move streaming message to history
                if let final = streamingMessage {
                    messages.append(final)
                    streamingMessage = nil
                    logger.info("[ViewModel] sendMessage finalized | sessionId=\(self.sessionId) finalContentLen=\(final.content.count)")
                } else {
                    logger.warning("[ViewModel] sendMessage no final assistant message | sessionId=\(self.sessionId)")
                }
            } catch {
                if !Task.isCancelled {
                    errorMessage = error.localizedDescription
                    logger.error("[ViewModel] sendMessage error | sessionId=\(self.sessionId) error=\(error.localizedDescription)")
                }
            }

            isSending = false
            logger.info("[ViewModel] sendMessage completed | sessionId=\(self.sessionId) totalMessages=\(self.messages.count)")
        }
    }

    func cancelStreaming() {
        logger.info("[ViewModel] cancelStreaming | sessionId=\(self.sessionId)")
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

    /// Start voice recording for chat message.
    func startVoiceRecording() async {
        do {
            try await dictationService.startRecording()
            isRecording = true
        } catch {
            logger.error("Failed to start recording: \(error.localizedDescription)")
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
            logger.error("Failed to transcribe: \(error.localizedDescription)")
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
