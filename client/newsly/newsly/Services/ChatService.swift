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

    /// Send a message and receive the assistant response (non-streaming)
    func sendMessage(
        sessionId: Int,
        message: String
    ) async throws -> ChatMessage {
        let request = SendChatMessageRequest(message: message)
        let encoder = JSONEncoder()
        let body = try encoder.encode(request)

        let response: SendChatMessageResponse = try await client.request(
            APIEndpoints.chatMessages(sessionId: sessionId),
            method: "POST",
            body: body
        )

        return response.assistantMessage
    }

    /// Get initial follow-up question suggestions for an article-based session (non-streaming)
    func getInitialSuggestions(
        sessionId: Int
    ) async throws -> ChatMessage {
        let response: InitialSuggestionsResponse = try await client.request(
            APIEndpoints.chatInitialSuggestions(sessionId: sessionId),
            method: "POST"
        )

        return ChatMessage(
            id: response.id,
            role: response.role,
            timestamp: response.timestamp,
            content: response.content
        )
    }

    // MARK: - Convenience Methods

    /// Start a deep dive chat for an article
    func startArticleChat(
        contentId: Int,
        provider: ChatModelProvider = .google
    ) async throws -> ChatSessionSummary {
        // Check for existing session
        if let existing = try await getSessionForContent(contentId: contentId) {
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
        provider: ChatModelProvider = .google
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
        provider: ChatModelProvider = .google
    ) async throws -> ChatSessionSummary {
        return try await createSession(
            provider: provider,
            initialMessage: initialMessage
        )
    }
}
