//
//  ScraperConfigService.swift
//  newsly
//

import Foundation

struct CreateScraperConfigPayload: Codable {
    let scraperType: String
    let displayName: String?
    let config: ScraperConfigBody
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
    let config: ScraperConfigBody?
    let isActive: Bool?

    enum CodingKeys: String, CodingKey {
        case displayName = "display_name"
        case config
        case isActive = "is_active"
    }
}

struct ScraperConfigBody: Codable {
    let feedURL: String?
    let limit: Int?

    enum CodingKeys: String, CodingKey {
        case feedURL = "feed_url"
        case limit
    }
}

class ScraperConfigService {
    static let shared = ScraperConfigService()
    private let client = APIClient.shared

    private init() {}

    func listConfigs(types: [String]? = nil) async throws -> [ScraperConfig] {
        var path = APIEndpoints.scraperConfigs
        if let types, !types.isEmpty {
            let typeParam = types.joined(separator: ",")
            path = "\(path)?types=\(typeParam)"
        }
        print("DEBUG: ScraperConfigService.listConfigs() - calling \(path)")
        let configs: [ScraperConfig] = try await client.request(path)
        print("DEBUG: ScraperConfigService.listConfigs() - received \(configs.count) configs")
        return configs
    }

    func createConfig(
        scraperType: String,
        displayName: String?,
        feedURL: String,
        limit: Int?,
        isActive: Bool
    ) async throws -> ScraperConfig {
        let payload = CreateScraperConfigPayload(
            scraperType: scraperType,
            displayName: displayName,
            config: ScraperConfigBody(feedURL: feedURL, limit: limit),
            isActive: isActive
        )
        let body = try JSONEncoder().encode(payload)
        return try await client.request(APIEndpoints.scraperConfigs, method: "POST", body: body)
    }

    func updateConfig(
        configId: Int,
        displayName: String?,
        feedURL: String?,
        limit: Int?,
        isActive: Bool?
    ) async throws -> ScraperConfig {
        let configBody = (feedURL != nil || limit != nil) ? ScraperConfigBody(feedURL: feedURL, limit: limit) : nil
        let payload = UpdateScraperConfigPayload(displayName: displayName, config: configBody, isActive: isActive)
        let body = try JSONEncoder().encode(payload)
        return try await client.request(APIEndpoints.scraperConfig(id: configId), method: "PUT", body: body)
    }

    func deleteConfig(configId: Int) async throws {
        try await client.requestVoid(APIEndpoints.scraperConfig(id: configId), method: "DELETE")
    }
}
