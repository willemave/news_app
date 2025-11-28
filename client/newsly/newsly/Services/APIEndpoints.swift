//
//  APIEndpoints.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

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
    static func tweetSuggestions(id: Int) -> String {
        return "/api/content/\(id)/tweet-suggestions"
    }
}
