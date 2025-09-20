//
//  ContentService.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

class ContentService {
    static let shared = ContentService()
    private let client = APIClient.shared
    
    private init() {}
    
    func searchContent(query: String,
                       contentType: String = "all",
                       limit: Int = 25,
                       offset: Int = 0) async throws -> ContentListResponse {
        let queryItems: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "type", value: contentType),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset))
        ]
        return try await client.request(APIEndpoints.searchContent, queryItems: queryItems)
    }

    func fetchContentList(contentType: String? = nil,
                         date: String? = nil,
                         readFilter: String = "all") async throws -> ContentListResponse {
        var queryItems: [URLQueryItem] = []
        
        if let contentType = contentType, contentType != "all" {
            queryItems.append(URLQueryItem(name: "content_type", value: contentType))
        }
        
        if let date = date, !date.isEmpty {
            queryItems.append(URLQueryItem(name: "date", value: date))
        }
        
        queryItems.append(URLQueryItem(name: "read_filter", value: readFilter))
        
        return try await client.request(APIEndpoints.contentList, queryItems: queryItems)
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
    
    func bulkMarkAsRead(contentIds: [Int]) async throws {
        struct BulkMarkReadRequest: Codable {
            let contentIds: [Int]
            
            enum CodingKeys: String, CodingKey {
                case contentIds = "content_ids"
            }
        }
        
        let request = BulkMarkReadRequest(contentIds: contentIds)
        let encoder = JSONEncoder()
        let body = try encoder.encode(request)
        
        try await client.requestVoid(APIEndpoints.bulkMarkRead, method: "POST", body: body)
    }
    
    func toggleFavorite(id: Int) async throws -> [String: Any] {
        return try await client.requestRaw(APIEndpoints.toggleFavorite(id: id), method: "POST")
    }
    
    func removeFavorite(id: Int) async throws {
        try await client.requestVoid(APIEndpoints.removeFavorite(id: id), method: "DELETE")
    }
    
    func toggleUnlike(id: Int) async throws -> [String: Any] {
        return try await client.requestRaw(APIEndpoints.toggleUnlike(id: id), method: "POST")
    }
    
    func removeUnlike(id: Int) async throws {
        try await client.requestVoid(APIEndpoints.removeUnlike(id: id), method: "DELETE")
    }
    
    func fetchFavoritesList() async throws -> ContentListResponse {
        return try await client.request(APIEndpoints.favoritesList)
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
}
