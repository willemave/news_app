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
    let structuredSummaryRaw: [String: AnyCodable]?
    let bulletPoints: [BulletPoint]
    let quotes: [Quote]
    let topics: [String]
    let fullMarkdown: String?
    let imageUrl: String?
    let thumbnailUrl: String?
    let detectedFeed: DetectedFeed?
    let canSubscribe: Bool?

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
        case structuredSummaryRaw = "structured_summary"
        case bulletPoints = "bullet_points"
        case quotes
        case topics
        case fullMarkdown = "full_markdown"
        case imageUrl = "image_url"
        case thumbnailUrl = "thumbnail_url"
        case detectedFeed = "detected_feed"
        case canSubscribe = "can_subscribe"
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

    // MARK: - Summary Type Detection

    /// Check if this content has an interleaved summary format
    var hasInterleavedSummary: Bool {
        guard let raw = structuredSummaryRaw,
              let summaryType = raw["summary_type"]?.value as? String else {
            return false
        }
        return summaryType == "interleaved"
    }

    /// Parse the raw summary as InterleavedSummary (returns nil if not interleaved format)
    var interleavedSummary: InterleavedSummary? {
        guard hasInterleavedSummary,
              let raw = structuredSummaryRaw else {
            return nil
        }

        let decoder = JSONDecoder()
        if let jsonData = try? JSONSerialization.data(withJSONObject: raw.mapValues { $0.value }) {
            return try? decoder.decode(InterleavedSummary.self, from: jsonData)
        }
        return nil
    }

    /// Parse the raw summary as StructuredSummary (returns nil if interleaved format)
    var structuredSummary: StructuredSummary? {
        guard !hasInterleavedSummary,
              let raw = structuredSummaryRaw else {
            return nil
        }

        let decoder = JSONDecoder()
        if let jsonData = try? JSONSerialization.data(withJSONObject: raw.mapValues { $0.value }) {
            return try? decoder.decode(StructuredSummary.self, from: jsonData)
        }
        return nil
    }
}
