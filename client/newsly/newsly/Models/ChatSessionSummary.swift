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
    let articleSummary: String?
    let articleSource: String?
    let hasPendingMessage: Bool?
    let isFavorite: Bool?
    let hasMessages: Bool?

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
        case articleSummary = "article_summary"
        case articleSource = "article_source"
        case hasPendingMessage = "has_pending_message"
        case isFavorite = "is_favorite"
        case hasMessages = "has_messages"
    }

    /// True if the session has a message currently being processed
    var isProcessing: Bool {
        hasPendingMessage ?? false
    }

    /// True if the linked content is favorited
    var isFavorited: Bool {
        isFavorite ?? false
    }

    /// True if the session has any messages
    var hasAnyMessages: Bool {
        hasMessages ?? true
    }

    /// True if this is a favorited article with no chat messages yet
    var isEmptyFavorite: Bool {
        isFavorited && !hasAnyMessages
    }

    var displayTitle: String {
        title ?? articleTitle ?? "Chat"
    }

    var displaySubtitle: String? {
        if let topic = topic, !topic.isEmpty {
            return topic
        }
        // For empty favorites, show the source
        if isEmptyFavorite, let source = articleSource {
            return source
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
        case "deep_research":
            return "Deep Research"
        default:
            return llmProvider.capitalized
        }
    }

    /// Returns the custom asset icon name for the provider
    var providerIconAsset: String? {
        switch llmProvider.lowercased() {
        case "openai":
            return "openai-icon"
        case "anthropic":
            return "claude-icon"
        case "google":
            return "gemini-icon"
        case "deep_research":
            return "deep-research-icon"
        default:
            return nil
        }
    }

    /// Returns a fallback SF Symbol if custom icon is not available
    var providerIconFallback: String {
        switch llmProvider.lowercased() {
        case "openai":
            return "brain.head.profile"
        case "anthropic":
            return "sparkles"
        case "google":
            return "diamond"
        case "deep_research":
            return "magnifyingglass.circle.fill"
        default:
            return "cpu"
        }
    }

    /// Whether this is a deep research session
    var isDeepResearch: Bool {
        sessionType == "deep_research" || llmProvider.lowercased() == "deep_research"
    }

    /// Icon name for the session type (used in chat list)
    var sessionTypeIconName: String {
        switch sessionType {
        case "voice_live":
            return "waveform.and.mic"
        case "deep_research":
            return "magnifyingglass.circle.fill"
        case "topic":
            return "text.magnifyingglass"
        case "article_brain":
            return "doc.text.magnifyingglass"
        case "ad_hoc":
            return "bubble.left.and.bubble.right"
        default:
            return "bubble.left"
        }
    }

    /// Human-readable label for the session type
    var sessionTypeLabel: String {
        switch sessionType {
        case "voice_live":
            return "Live Voice"
        case "deep_research":
            return "Deep Research"
        case "topic":
            return "Search"
        case "article_brain":
            return "Dig Deeper"
        case "ad_hoc":
            return "Chat"
        default:
            return "Chat"
        }
    }
}
