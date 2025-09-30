//
//  ContentListResponse.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

struct ContentListResponse: Codable {
    let contents: [ContentSummary]
    let availableDates: [String]
    let contentTypes: [String]
    let total: Int
    let nextCursor: String?
    let hasMore: Bool
    let pageSize: Int

    enum CodingKeys: String, CodingKey {
        case contents
        case availableDates = "available_dates"
        case contentTypes = "content_types"
        case total
        case nextCursor = "next_cursor"
        case hasMore = "has_more"
        case pageSize = "page_size"
    }
}