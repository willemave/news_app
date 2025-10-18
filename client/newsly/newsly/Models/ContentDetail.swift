//
//  ContentDetail.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

struct ContentDetail: Codable, Identifiable {
    let id: Int
    let contentType: String
    let url: String
    let title: String?
    let displayTitle: String
    let source: String?
    let status: String
    let errorMessage: String?
    let retryCount: Int
    let metadata: [String: AnyCodable]
    let createdAt: String
    let updatedAt: String?
    let processedAt: String?
    let checkedOutBy: String?
    let checkedOutAt: String?
    let publicationDate: String?
    var isRead: Bool
    var isFavorited: Bool
    let summary: String?
    let shortSummary: String?
    let structuredSummary: StructuredSummary?
    let bulletPoints: [BulletPoint]
    let quotes: [Quote]
    let topics: [String]
    let fullMarkdown: String?
    let isAggregate: Bool
    let renderedMarkdown: String?
    let newsItems: [NewsItem]?
    
    enum CodingKeys: String, CodingKey {
        case id
        case contentType = "content_type"
        case url
        case title
        case displayTitle = "display_title"
        case source
        case status
        case errorMessage = "error_message"
        case retryCount = "retry_count"
        case metadata
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case processedAt = "processed_at"
        case checkedOutBy = "checked_out_by"
        case checkedOutAt = "checked_out_at"
        case publicationDate = "publication_date"
        case isRead = "is_read"
        case isFavorited = "is_favorited"
        case summary
        case shortSummary = "short_summary"
        case structuredSummary = "structured_summary"
        case bulletPoints = "bullet_points"
        case quotes
        case topics
        case fullMarkdown = "full_markdown"
        case isAggregate = "is_aggregate"
        case renderedMarkdown = "rendered_markdown"
        case newsItems = "news_items"
    }
    
    var contentTypeEnum: ContentType? {
        ContentType(rawValue: contentType)
    }
    
    var articleMetadata: ArticleMetadata? {
        guard contentType == "article" else { return nil }
        
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        
        if let jsonData = try? JSONSerialization.data(withJSONObject: metadata.mapValues { $0.value }) {
            return try? decoder.decode(ArticleMetadata.self, from: jsonData)
        }
        return nil
    }
    
    var podcastMetadata: PodcastMetadata? {
        guard contentType == "podcast" else { return nil }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        if let jsonData = try? JSONSerialization.data(withJSONObject: metadata.mapValues { $0.value }) {
            return try? decoder.decode(PodcastMetadata.self, from: jsonData)
        }
        return nil
    }

    var newsMetadata: NewsMetadata? {
        guard contentType == "news" else { return nil }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        if let jsonData = try? JSONSerialization.data(withJSONObject: metadata.mapValues { $0.value }) {
            return try? decoder.decode(NewsMetadata.self, from: jsonData)
        }
        return nil
    }
}

struct NewsItem: Codable, Identifiable {
    let title: String?
    let url: String
    let summary: String?
    let source: String?
    let author: String?
    let metadata: [String: AnyCodable]?
    let commentsUrl: String?
    let bulletPoints: [BulletPoint]?

    enum CodingKeys: String, CodingKey {
        case title
        case url
        case summary
        case source
        case author
        case metadata
        case commentsUrl = "comments_url"
        case bulletPoints = "bullet_points"
    }

    var id: String { url }
}
