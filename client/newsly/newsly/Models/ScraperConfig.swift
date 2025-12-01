//
//  ScraperConfig.swift
//  newsly
//

import Foundation

struct ScraperConfig: Identifiable, Codable {
    let id: Int
    let scraperType: String
    let displayName: String?
    let config: [String: AnyCodable]
    let limit: Int?
    let isActive: Bool
    let createdAt: String

    var feedURL: String? {
        if let feedValue = config["feed_url"]?.value as? String {
            return feedValue
        }
        if let urlValue = config["url"]?.value as? String {
            return urlValue
        }
        return nil
    }

    enum CodingKeys: String, CodingKey {
        case id
        case scraperType = "scraper_type"
        case displayName = "display_name"
        case config
        case limit
        case isActive = "is_active"
        case createdAt = "created_at"
    }
}
