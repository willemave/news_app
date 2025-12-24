//
//  APIEndpoints.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Combine
import Foundation

enum APIEndpoints {
    static let contentList = "/api/content/"
    static let submitContent = "/api/content/submit"
    static let searchContent = "/api/content/search"
    static func contentDetail(id: Int) -> String {
        return "/api/content/\(id)"
    }
    static func markContentRead(id: Int) -> String {
        return "/api/content/\(id)/mark-read"
    }
    static func markContentUnread(id: Int) -> String {
        return "/api/content/\(id)/mark-unread"
    }
    static let bulkMarkRead = "/api/content/bulk-mark-read"
    static func toggleFavorite(id: Int) -> String {
        return "/api/content/\(id)/favorite"
    }
    static func removeFavorite(id: Int) -> String {
        return "/api/content/\(id)/unfavorite"
    }
    static let favoritesList = "/api/content/favorites/list"
    static let recentlyReadList = "/api/content/recently-read/list"
    static func chatGPTUrl(id: Int) -> String {
        return "/api/content/\(id)/chat-url"
    }
    static let unreadCounts = "/api/content/unread-counts"
    static func convertNewsToArticle(id: Int) -> String {
        return "/api/content/\(id)/convert-to-article"
    }
    static let scraperConfigs = "/api/scrapers/"
    static func scraperConfig(id: Int) -> String {
        return "/api/scrapers/\(id)"
    }
    static let subscribeFeed = "/api/scrapers/subscribe"
    static func tweetSuggestions(id: Int) -> String {
        return "/api/content/\(id)/tweet-suggestions"
    }

    // MARK: - Chat Endpoints
    static let chatSessions = "/api/content/chat/sessions"
    static func chatSession(id: Int) -> String {
        return "/api/content/chat/sessions/\(id)"
    }
    static func chatMessages(sessionId: Int) -> String {
        return "/api/content/chat/sessions/\(sessionId)/messages"
    }
    static func chatInitialSuggestions(sessionId: Int) -> String {
        return "/api/content/chat/sessions/\(sessionId)/initial-suggestions"
    }
    static func chatMessageStatus(messageId: Int) -> String {
        return "/api/content/chat/messages/\(messageId)/status"
    }
}
