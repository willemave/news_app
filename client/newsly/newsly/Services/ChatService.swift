//
//  ChatService.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "ChatService")

class ChatService {
    static let shared = ChatService()
    private let client = APIClient.shared

    private init() {}

    // MARK: - Session Management

    /// List all chat sessions for the current user
    func listSessions(
        contentId: Int? = nil,
        limit: Int = 50
    ) async throws -> [ChatSessionSummary] {
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit))
        ]

        if let contentId = contentId {
            queryItems.append(URLQueryItem(name: "content_id", value: String(contentId)))
        }

        return try await client.request(
            APIEndpoints.chatSessions,
            queryItems: queryItems
        )
    }

    /// Create a new chat session
    func createSession(
        contentId: Int? = nil,
        topic: String? = nil,
        provider: ChatModelProvider? = nil,
        modelHint: String? = nil,
        initialMessage: String? = nil
    ) async throws -> ChatSessionSummary {
        let request = CreateChatSessionRequest(
            contentId: contentId,
            topic: topic,
            llmProvider: provider?.rawValue,
            llmModelHint: modelHint,
            initialMessage: initialMessage
        )

        let encoder = JSONEncoder()
        let body = try encoder.encode(request)

        let response: CreateChatSessionResponse = try await client.request(
            APIEndpoints.chatSessions,
            method: "POST",
            body: body
        )

        logger.info("Created chat session id=\(response.session.id)")
        return response.session
    }

    /// Get session details with message history
    func getSession(id: Int) async throws -> ChatSessionDetail {
        return try await client.request(APIEndpoints.chatSession(id: id))
    }

    /// Check if a session exists for the given content
    func getSessionForContent(contentId: Int) async throws -> ChatSessionSummary? {
        let sessions = try await listSessions(contentId: contentId, limit: 1)
        return sessions.first
    }

    // MARK: - Messaging

    /// Send a message and stream the response
    func sendMessage(
        sessionId: Int,
        message: String
    ) -> AsyncThrowingStream<ChatMessage, Error> {
        logger.info("[ChatService] sendMessage started | sessionId=\(sessionId) messageLen=\(message.count)")
        let request = SendChatMessageRequest(message: message)

        do {
            let encoder = JSONEncoder()
            let body = try encoder.encode(request)
            logger.debug("[ChatService] sendMessage request encoded | sessionId=\(sessionId)")

            return client.streamNDJSON(
                APIEndpoints.chatMessages(sessionId: sessionId),
                method: "POST",
                body: body
            )
        } catch {
            logger.error("[ChatService] sendMessage encode error | sessionId=\(sessionId) error=\(error.localizedDescription)")
            return AsyncThrowingStream { continuation in
                continuation.finish(throwing: error)
            }
        }
    }

    /// Send a message and wait for the complete response
    func sendMessageSync(
        sessionId: Int,
        message: String
    ) async throws -> ChatMessage? {
        logger.info("[ChatService] sendMessageSync started | sessionId=\(sessionId)")
        var lastMessage: ChatMessage?
        var messageCount = 0

        for try await msg in sendMessage(sessionId: sessionId, message: message) {
            messageCount += 1
            if msg.role == .assistant {
                lastMessage = msg
                logger.debug("[ChatService] sendMessageSync assistant msg #\(messageCount) | contentLen=\(msg.content.count)")
            }
        }

        logger.info("[ChatService] sendMessageSync completed | sessionId=\(sessionId) totalMessages=\(messageCount)")
        return lastMessage
    }

    /// Get initial follow-up question suggestions for an article-based session
    func getInitialSuggestions(
        sessionId: Int
    ) -> AsyncThrowingStream<ChatMessage, Error> {
        logger.info("[ChatService] getInitialSuggestions started | sessionId=\(sessionId)")
        return client.streamNDJSON(
            APIEndpoints.chatInitialSuggestions(sessionId: sessionId),
            method: "POST",
            body: nil
        )
    }

    // MARK: - Convenience Methods

    /// Start a deep dive chat for an article
    func startArticleChat(
        contentId: Int,
        provider: ChatModelProvider = .openai
    ) async throws -> ChatSessionSummary {
        // Check for existing session
        if let existing = try await getSessionForContent(contentId: contentId) {
            logger.info("Using existing session id=\(existing.id) for content id=\(contentId)")
            return existing
        }

        // Create new session
        return try await createSession(
            contentId: contentId,
            provider: provider
        )
    }

    /// Start a topic-focused chat for an article
    func startTopicChat(
        contentId: Int,
        topic: String,
        provider: ChatModelProvider = .openai
    ) async throws -> ChatSessionSummary {
        return try await createSession(
            contentId: contentId,
            topic: topic,
            provider: provider
        )
    }

    /// Start an ad-hoc chat without article context
    func startAdHocChat(
        initialMessage: String? = nil,
        provider: ChatModelProvider = .openai
    ) async throws -> ChatSessionSummary {
        return try await createSession(
            provider: provider,
            initialMessage: initialMessage
        )
    }
}
