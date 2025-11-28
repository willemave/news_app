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
