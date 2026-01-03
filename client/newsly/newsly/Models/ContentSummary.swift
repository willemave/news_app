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
    let imageUrl: String?
    let thumbnailUrl: String?

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
        case imageUrl = "image_url"
        case thumbnailUrl = "thumbnail_url"
    }

    init(
        id: Int,
        contentType: String,
        url: String,
        title: String?,
        source: String?,
        platform: String?,
        status: String,
        shortSummary: String?,
        createdAt: String,
        processedAt: String?,
        classification: String?,
        publicationDate: String?,
        isRead: Bool,
        isFavorited: Bool,
        imageUrl: String? = nil,
        thumbnailUrl: String? = nil
    ) {
        self.id = id
        self.contentType = contentType
        self.url = url
        self.title = title
        self.source = source
        self.platform = platform
        self.status = status
        self.shortSummary = shortSummary
        self.createdAt = createdAt
        self.processedAt = processedAt
        self.classification = classification
        self.publicationDate = publicationDate
        self.isRead = isRead
        self.isFavorited = isFavorited
        self.imageUrl = imageUrl
        self.thumbnailUrl = thumbnailUrl
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.init(
            id: try container.decode(Int.self, forKey: .id),
            contentType: try container.decode(String.self, forKey: .contentType),
            url: try container.decode(String.self, forKey: .url),
            title: try container.decodeIfPresent(String.self, forKey: .title),
            source: try container.decodeIfPresent(String.self, forKey: .source),
            platform: try container.decodeIfPresent(String.self, forKey: .platform),
            status: try container.decode(String.self, forKey: .status),
            shortSummary: try container.decodeIfPresent(String.self, forKey: .shortSummary),
            createdAt: try container.decode(String.self, forKey: .createdAt),
            processedAt: try container.decodeIfPresent(String.self, forKey: .processedAt),
            classification: try container.decodeIfPresent(String.self, forKey: .classification),
            publicationDate: try container.decodeIfPresent(String.self, forKey: .publicationDate),
            isRead: try container.decode(Bool.self, forKey: .isRead),
            isFavorited: try container.decodeIfPresent(Bool.self, forKey: .isFavorited) ?? false,
            imageUrl: try container.decodeIfPresent(String.self, forKey: .imageUrl),
            thumbnailUrl: try container.decodeIfPresent(String.self, forKey: .thumbnailUrl)
        )
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(contentType, forKey: .contentType)
        try container.encode(url, forKey: .url)
        try container.encodeIfPresent(title, forKey: .title)
        try container.encodeIfPresent(source, forKey: .source)
        try container.encodeIfPresent(platform, forKey: .platform)
        try container.encode(status, forKey: .status)
        try container.encodeIfPresent(shortSummary, forKey: .shortSummary)
        try container.encode(createdAt, forKey: .createdAt)
        try container.encodeIfPresent(processedAt, forKey: .processedAt)
        try container.encodeIfPresent(classification, forKey: .classification)
        try container.encodeIfPresent(publicationDate, forKey: .publicationDate)
        try container.encode(isRead, forKey: .isRead)
        try container.encode(isFavorited, forKey: .isFavorited)
        try container.encodeIfPresent(imageUrl, forKey: .imageUrl)
        try container.encodeIfPresent(thumbnailUrl, forKey: .thumbnailUrl)
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
        return nil
    }

    var formattedDate: String {
        let dateString = processedAt ?? createdAt
        guard let date = parseDate(from: dateString) else {
            return "Date unknown"
        }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        displayFormatter.timeZone = TimeZone.current
        return displayFormatter.string(from: date)
    }

    var processedDateDisplay: String? {
        guard let processedAt, let date = parseDate(from: processedAt) else {
            return nil
        }

        let displayFormatter = DateFormatter()
        displayFormatter.dateFormat = "MM-dd-yyyy"
        displayFormatter.timeZone = TimeZone.current
        return displayFormatter.string(from: date)
    }

    func updating(
        isRead: Bool? = nil,
        isFavorited: Bool? = nil
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
            imageUrl: imageUrl,
            thumbnailUrl: thumbnailUrl
        )
    }

    private func parseDate(from dateString: String) -> Date? {
        let iso8601WithFractional = ISO8601DateFormatter()
        iso8601WithFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso8601WithFractional.date(from: dateString) {
            return date
        }

        let iso8601 = ISO8601DateFormatter()
        iso8601.formatOptions = [.withInternetDateTime]
        if let date = iso8601.date(from: dateString) {
            return date
        }

        let formatterWithMicroseconds = DateFormatter()
        formatterWithMicroseconds.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        formatterWithMicroseconds.timeZone = TimeZone(abbreviation: "UTC")
        if let date = formatterWithMicroseconds.date(from: dateString) {
            return date
        }

        let formatterWithoutMicroseconds = DateFormatter()
        formatterWithoutMicroseconds.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        formatterWithoutMicroseconds.timeZone = TimeZone(abbreviation: "UTC")
        if let date = formatterWithoutMicroseconds.date(from: dateString) {
            return date
        }

        return nil
    }
}
