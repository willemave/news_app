//
//  ChatSessionDetail.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import Foundation

/// Full chat session details with message history
struct ChatSessionDetail: Codable {
    let session: ChatSessionSummary
    let messages: [ChatMessage]
}

/// Response from creating a new chat session
struct CreateChatSessionResponse: Codable {
    let session: ChatSessionSummary
}

/// Response after sending a message (non-streaming)
struct SendChatMessageResponse: Codable {
    let sessionId: Int
    let assistantMessage: ChatMessage

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case assistantMessage = "assistant_message"
    }
}

/// Response for initial suggestions (non-streaming)
struct InitialSuggestionsResponse: Codable {
    let id: Int
    let sessionId: Int
    let role: ChatMessageRole
    let content: String
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case id
        case sessionId = "session_id"
        case role
        case content
        case timestamp
    }
}

/// Request to create a new chat session
struct CreateChatSessionRequest: Codable {
    var contentId: Int?
    var topic: String?
    var llmProvider: String?
    var llmModelHint: String?
    var initialMessage: String?

    enum CodingKeys: String, CodingKey {
        case contentId = "content_id"
        case topic
        case llmProvider = "llm_provider"
        case llmModelHint = "llm_model_hint"
        case initialMessage = "initial_message"
    }
}

/// Request to send a message in a chat session
struct SendChatMessageRequest: Codable {
    let message: String
}
