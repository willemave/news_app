//
//  ContentService.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

struct BulkMarkReadResponse: Codable {
    let status: String
    let markedCount: Int
    let failedIds: [Int]
    let totalRequested: Int

    enum CodingKeys: String, CodingKey {
        case status
        case markedCount = "marked_count"
        case failedIds = "failed_ids"
        case totalRequested = "total_requested"
    }
}

struct ConvertNewsResponse: Codable {
    let status: String
    let newContentId: Int
    let originalContentId: Int
    let alreadyExists: Bool
    let message: String

    enum CodingKeys: String, CodingKey {
        case status
        case newContentId = "new_content_id"
        case originalContentId = "original_content_id"
        case alreadyExists = "already_exists"
        case message
    }
}

class ContentService {
    static let shared = ContentService()
    private let client = APIClient.shared
    
    private init() {}
    
    func searchContent(query: String,
                       contentType: String = "all",
                       limit: Int = 25,
                       cursor: String? = nil) async throws -> ContentListResponse {
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "type", value: contentType),
            URLQueryItem(name: "limit", value: String(limit))
        ]

        if let cursor = cursor {
            queryItems.append(URLQueryItem(name: "cursor", value: cursor))
        }

        return try await client.request(APIEndpoints.searchContent, queryItems: queryItems)
    }

    func fetchContentList(contentTypes: [String]? = nil,
                         date: String? = nil,
                         readFilter: String = "all",
                         cursor: String? = nil,
                         limit: Int = 25) async throws -> ContentListResponse {
        var queryItems: [URLQueryItem] = []

        // Support multiple content_type parameters
        if let contentTypes = contentTypes, !contentTypes.isEmpty {
            // Don't filter if contains "all"
            let types = contentTypes.filter { $0 != "all" }
            if !types.isEmpty {
                // Add multiple content_type query parameters
                for type in types {
                    queryItems.append(URLQueryItem(name: "content_type", value: type))
                }
            }
        }

        if let date = date, !date.isEmpty {
            queryItems.append(URLQueryItem(name: "date", value: date))
        }

        queryItems.append(URLQueryItem(name: "read_filter", value: readFilter))
        queryItems.append(URLQueryItem(name: "limit", value: String(limit)))

        if let cursor = cursor {
            queryItems.append(URLQueryItem(name: "cursor", value: cursor))
        }

        return try await client.request(APIEndpoints.contentList, queryItems: queryItems)
    }

    // Backward compatibility: single content type
    func fetchContentList(contentType: String? = nil,
                         date: String? = nil,
                         readFilter: String = "all",
                         cursor: String? = nil,
                         limit: Int = 25) async throws -> ContentListResponse {
        let types = contentType.map { [$0] }
        return try await fetchContentList(contentTypes: types, date: date, readFilter: readFilter, cursor: cursor, limit: limit)
    }
    
    func fetchContentDetail(id: Int) async throws -> ContentDetail {
        return try await client.request(APIEndpoints.contentDetail(id: id))
    }
    
    func markContentAsRead(id: Int) async throws {
        try await client.requestVoid(APIEndpoints.markContentRead(id: id), method: "POST")
    }
    
    func markContentAsUnread(id: Int) async throws {
        try await client.requestVoid(APIEndpoints.markContentUnread(id: id), method: "DELETE")
    }
    
    func bulkMarkAsRead(contentIds: [Int]) async throws -> BulkMarkReadResponse {
        struct BulkMarkReadRequest: Codable {
            let contentIds: [Int]
            
            enum CodingKeys: String, CodingKey {
                case contentIds = "content_ids"
            }
        }
        
        let request = BulkMarkReadRequest(contentIds: contentIds)
        let encoder = JSONEncoder()
        let body = try encoder.encode(request)
        
        return try await client.request(
            APIEndpoints.bulkMarkRead,
            method: "POST",
            body: body
        )
    }

    func markAllAsRead(contentType: String) async throws -> BulkMarkReadResponse? {
        var allUnreadIds: [Int] = []
        var cursor: String? = nil

        // Loop through all pages until hasMore is false
        repeat {
            let response = try await fetchContentList(
                contentType: contentType,
                readFilter: "unread",
                cursor: cursor,
                limit: 100  // Fetch larger batches for efficiency
            )

            // Collect unread IDs from this page
            let pageUnreadIds = response.contents
                .filter { !$0.isRead }
                .map { $0.id }

            allUnreadIds.append(contentsOf: pageUnreadIds)

            // Update cursor for next iteration
            cursor = response.nextCursor

            // Continue if there are more pages
            if !response.hasMore {
                break
            }
        } while cursor != nil

        guard !allUnreadIds.isEmpty else {
            return nil
        }

        return try await bulkMarkAsRead(contentIds: allUnreadIds)
    }
    
    func toggleFavorite(id: Int) async throws -> [String: Any] {
        return try await client.requestRaw(APIEndpoints.toggleFavorite(id: id), method: "POST")
    }
    
    func removeFavorite(id: Int) async throws {
        try await client.requestVoid(APIEndpoints.removeFavorite(id: id), method: "DELETE")
    }

    func fetchFavoritesList(cursor: String? = nil, limit: Int = 25) async throws -> ContentListResponse {
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit))
        ]

        if let cursor = cursor {
            queryItems.append(URLQueryItem(name: "cursor", value: cursor))
        }

        return try await client.request(APIEndpoints.favoritesList, queryItems: queryItems)
    }

    func fetchRecentlyReadList(cursor: String? = nil, limit: Int = 25) async throws -> ContentListResponse {
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit))
        ]

        if let cursor = cursor {
            queryItems.append(URLQueryItem(name: "cursor", value: cursor))
        }

        return try await client.request(APIEndpoints.recentlyReadList, queryItems: queryItems)
    }

    func getChatGPTUrl(id: Int) async throws -> String {
        struct ChatGPTUrlResponse: Codable {
            let chatUrl: String
            let truncated: Bool

            enum CodingKeys: String, CodingKey {
                case chatUrl = "chat_url"
                case truncated
            }
        }

        let response: ChatGPTUrlResponse = try await client.request(APIEndpoints.chatGPTUrl(id: id))
        return response.chatUrl
    }

    func convertNewsToArticle(id: Int) async throws -> ConvertNewsResponse {
        return try await client.request(
            APIEndpoints.convertNewsToArticle(id: id),
            method: "POST"
        )
    }
}
