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

    private let chatService = ChatService.shared
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
            logger.error("Failed to load session \(self.sessionId): \(error.localizedDescription)")
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
                    // Don't show error for initial suggestions - just log it
                    logger.error("Failed to load initial suggestions: \(error.localizedDescription)")
                }
            }

            isSending = false
        }
    }

    func sendMessage() async {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }

        inputText = ""
        isSending = true
        errorMessage = nil

        // Cancel any existing stream
        streamTask?.cancel()

        streamTask = Task {
            do {
                for try await message in chatService.sendMessage(sessionId: sessionId, message: text) {
                    if Task.isCancelled { break }

                    if message.role == .user {
                        // Add user message to history
                        messages.append(message)
                    } else if message.role == .assistant {
                        // Update streaming message (each chunk replaces the previous)
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
                    logger.error("Send message failed: \(error.localizedDescription)")
                }
            }

            isSending = false
        }
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
}
