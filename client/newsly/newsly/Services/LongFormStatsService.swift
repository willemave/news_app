//
//  LongFormStatsService.swift
//  newsly
//
//  Created by Assistant on 1/16/26.
//

import Combine
import Foundation

struct LongFormStatsResponse: Codable {
    let totalCount: Int
    let unreadCount: Int
    let readCount: Int
    let savedToKnowledgeCount: Int
    let processingCount: Int

    enum CodingKeys: String, CodingKey {
        case totalCount = "total_count"
        case unreadCount = "unread_count"
        case readCount = "read_count"
        case savedToKnowledgeCount = "saved_to_knowledge_count"
        case processingCount = "processing_count"
    }
}

@MainActor
final class LongFormStatsService: ObservableObject {
    static let shared = LongFormStatsService()

    @Published var totalCount: Int = 0
    @Published var unreadCount: Int = 0
    @Published var readCount: Int = 0
    @Published var savedToKnowledgeCount: Int = 0
    @Published var processingCount: Int = 0

    private let client = APIClient.shared

    private init() {}

    func refreshStats() async {
        do {
            let response: LongFormStatsResponse = try await client.request(APIEndpoints.longFormStats)
            totalCount = response.totalCount
            unreadCount = response.unreadCount
            readCount = response.readCount
            savedToKnowledgeCount = response.savedToKnowledgeCount
            processingCount = response.processingCount
        } catch {
            print("Failed to fetch long-form stats: \(error)")
        }
    }
}
