//
//  ContentSummary.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

struct ContentSummary: Codable, Identifiable {
    let id: Int
    let contentType: String
    let url: String
    let title: String?
    let source: String?
    let platform: String?
    let status: String
    let shortSummary: String?
    let createdAt: String
    let processedAt: String?
    let classification: String?
    let publicationDate: String?
    let isRead: Bool
    var isFavorited: Bool
    var isUnliked: Bool
    let isAggregate: Bool
    let itemCount: Int?
    
    enum CodingKeys: String, CodingKey {
        case id
        case contentType = "content_type"
        case url
        case title
        case source
        case platform
        case status
        case shortSummary = "short_summary"
        case createdAt = "created_at"
        case processedAt = "processed_at"
        case classification
        case publicationDate = "publication_date"
        case isRead = "is_read"
        case isFavorited = "is_favorited"
        case isUnliked = "is_unliked"
        case isAggregate = "is_aggregate"
        case itemCount = "item_count"
    }

    var contentTypeEnum: ContentType? {
        ContentType(rawValue: contentType)
    }

    var displayTitle: String {
        title ?? "Untitled"
    }

    var secondaryLine: String? {
        if let summary = shortSummary, !summary.isEmpty {
            return summary
        }
        if contentType == "news" {
            if let count = itemCount, count > 0 {
                return isAggregate ? "\(count) updates" : nil
            }
        }
        return nil
    }

    var formattedDate: String {
        let dateString = processedAt ?? createdAt
        
        // Try multiple date formats
        var date: Date?
        
        // Try ISO8601 with fractional seconds
        let iso8601WithFractional = ISO8601DateFormatter()
        iso8601WithFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        date = iso8601WithFractional.date(from: dateString)
        
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
        
        // Try without microseconds
        if date == nil {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
            formatter.timeZone = TimeZone(abbreviation: "UTC")
            date = formatter.date(from: dateString)
        }
        
        guard let date = date else { 
            return "Date unknown" 
        }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        displayFormatter.timeZone = TimeZone.current
        return displayFormatter.string(from: date)
    }

    func updating(
        isRead: Bool? = nil,
        isFavorited: Bool? = nil,
        isUnliked: Bool? = nil
    ) -> ContentSummary {
        ContentSummary(
            id: id,
            contentType: contentType,
            url: url,
            title: title,
            source: source,
            platform: platform,
            status: status,
            shortSummary: shortSummary,
            createdAt: createdAt,
            processedAt: processedAt,
            classification: classification,
            publicationDate: publicationDate,
            isRead: isRead ?? self.isRead,
            isFavorited: isFavorited ?? self.isFavorited,
            isUnliked: isUnliked ?? self.isUnliked,
            isAggregate: isAggregate,
            itemCount: itemCount
        )
    }
}
