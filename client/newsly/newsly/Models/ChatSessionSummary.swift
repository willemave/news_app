//
//  ChatSessionSummary.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import Foundation

/// Summary of a chat session for list view
struct ChatSessionSummary: Codable, Identifiable, Hashable {
    static func == (lhs: ChatSessionSummary, rhs: ChatSessionSummary) -> Bool {
        lhs.id == rhs.id
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
    let id: Int
    let contentId: Int?
    let title: String?
    let sessionType: String?
    let topic: String?
    let llmProvider: String
    let llmModel: String
    let createdAt: String
    let updatedAt: String?
    let lastMessageAt: String?
    let articleTitle: String?
    let articleUrl: String?

    enum CodingKeys: String, CodingKey {
        case id
        case contentId = "content_id"
        case title
        case sessionType = "session_type"
        case topic
        case llmProvider = "llm_provider"
        case llmModel = "llm_model"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case lastMessageAt = "last_message_at"
        case articleTitle = "article_title"
        case articleUrl = "article_url"
    }

    var displayTitle: String {
        title ?? articleTitle ?? "Chat"
    }

    var displaySubtitle: String? {
        if let topic = topic, !topic.isEmpty {
            return topic
        }
        if sessionType == "article_brain", let articleTitle = articleTitle {
            return "About: \(articleTitle)"
        }
        return nil
    }

    var formattedDate: String {
        let dateString = lastMessageAt ?? createdAt

        // Try ISO8601 with fractional seconds
        let iso8601WithFractional = ISO8601DateFormatter()
        iso8601WithFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = iso8601WithFractional.date(from: dateString)

        // Try ISO8601 without fractional seconds
        if date == nil {
            let iso8601 = ISO8601DateFormatter()
            iso8601.formatOptions = [.withInternetDateTime]
            date = iso8601.date(from: dateString)
        }

        // Try basic ISO format
        if date == nil {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
            formatter.timeZone = TimeZone(abbreviation: "UTC")
            date = formatter.date(from: dateString)
        }

        guard let date = date else {
            return "Date unknown"
        }

        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .short
        displayFormatter.timeStyle = .short
        displayFormatter.timeZone = TimeZone.current
        return displayFormatter.string(from: date)
    }

    var providerDisplayName: String {
        switch llmProvider.lowercased() {
        case "openai":
            return "GPT"
        case "anthropic":
            return "Claude"
        case "google":
            return "Gemini"
        default:
            return llmProvider.capitalized
        }
    }
}
