//
//  DiscoveryService.swift
//  newsly
//

import Foundation

struct DiscoverySuggestionIdsPayload: Codable {
    let suggestionIds: [Int]

    enum CodingKeys: String, CodingKey {
        case suggestionIds = "suggestion_ids"
    }
}

class DiscoveryService {
    static let shared = DiscoveryService()
    private let client = APIClient.shared

    private init() {}

    func fetchSuggestions() async throws -> DiscoverySuggestionsResponse {
        try await client.request(APIEndpoints.discoverySuggestions)
    }

    func fetchHistory(limit: Int = 6) async throws -> DiscoveryHistoryResponse {
        let queryItems = [URLQueryItem(name: "limit", value: String(limit))]
        return try await client.request(APIEndpoints.discoveryHistory, queryItems: queryItems)
    }

    func refresh() async throws -> DiscoveryRefreshResponse {
        try await client.request(APIEndpoints.discoveryRefresh, method: "POST")
    }

    func subscribe(suggestionIds: [Int]) async throws -> DiscoverySubscribeResponse {
        let payload = DiscoverySuggestionIdsPayload(suggestionIds: suggestionIds)
        let body = try JSONEncoder().encode(payload)
        return try await client.request(APIEndpoints.discoverySubscribe, method: "POST", body: body)
    }

    func addItems(suggestionIds: [Int]) async throws -> DiscoveryAddItemResponse {
        let payload = DiscoverySuggestionIdsPayload(suggestionIds: suggestionIds)
        let body = try JSONEncoder().encode(payload)
        return try await client.request(APIEndpoints.discoveryAddItem, method: "POST", body: body)
    }

    func dismiss(suggestionIds: [Int]) async throws -> DiscoveryDismissResponse {
        let payload = DiscoverySuggestionIdsPayload(suggestionIds: suggestionIds)
        let body = try JSONEncoder().encode(payload)
        return try await client.request(APIEndpoints.discoveryDismiss, method: "POST", body: body)
    }

    func clear() async throws -> DiscoveryDismissResponse {
        try await client.request(APIEndpoints.discoveryClear, method: "POST")
    }
}
