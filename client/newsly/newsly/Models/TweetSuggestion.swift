//
//  TweetSuggestion.swift
//  newsly
//
//  Tweet suggestion models for social sharing.
//

import Foundation

/// A single tweet suggestion from the LLM.
struct TweetSuggestion: Codable, Identifiable {
    let id: Int
    let text: String
    let styleLabel: String?

    enum CodingKeys: String, CodingKey {
        case id
        case text
        case styleLabel = "style_label"
    }
}

/// Request to generate tweet suggestions.
struct TweetSuggestionsRequest: Codable {
    let message: String?
    let creativity: Int

    init(message: String? = nil, creativity: Int = 5) {
        self.message = message
        self.creativity = creativity
    }
}

/// Response containing generated tweet suggestions.
struct TweetSuggestionsResponse: Codable {
    let contentId: Int
    let creativity: Int
    let model: String
    let suggestions: [TweetSuggestion]

    enum CodingKeys: String, CodingKey {
        case contentId = "content_id"
        case creativity
        case model
        case suggestions
    }
}
