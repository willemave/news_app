//
//  ScraperConfigService.swift
//  newsly
//

import Foundation

struct CreateScraperConfigPayload: Codable {
    let scraperType: String
    let displayName: String?
    let config: [String: String]
    let isActive: Bool

    enum CodingKeys: String, CodingKey {
        case scraperType = "scraper_type"
        case displayName = "display_name"
        case config
        case isActive = "is_active"
    }
}

struct UpdateScraperConfigPayload: Codable {
    let displayName: String?
    let config: [String: String]?
    let isActive: Bool?

    enum CodingKeys: String, CodingKey {
        case displayName = "display_name"
        case config
        case isActive = "is_active"
    }
}

class ScraperConfigService {
    static let shared = ScraperConfigService()
    private let client = APIClient.shared

    private init() {}

    func listConfigs() async throws -> [ScraperConfig] {
        try await client.request(APIEndpoints.scraperConfigs)
    }

    func createConfig(scraperType: String, displayName: String?, feedURL: String, isActive: Bool) async throws -> ScraperConfig {
        let payload = CreateScraperConfigPayload(
            scraperType: scraperType,
            displayName: displayName,
            config: ["feed_url": feedURL],
            isActive: isActive
        )
        let body = try JSONEncoder().encode(payload)
        return try await client.request(APIEndpoints.scraperConfigs, method: "POST", body: body)
    }

    func updateConfig(configId: Int, displayName: String?, feedURL: String?, isActive: Bool?) async throws -> ScraperConfig {
        let payload = UpdateScraperConfigPayload(
            displayName: displayName,
            config: feedURL.map { ["feed_url": $0] },
            isActive: isActive
        )
        let body = try JSONEncoder().encode(payload)
        return try await client.request(APIEndpoints.scraperConfig(id: configId), method: "PUT", body: body)
    }

    func deleteConfig(configId: Int) async throws {
        try await client.requestVoid(APIEndpoints.scraperConfig(id: configId), method: "DELETE")
    }
}
