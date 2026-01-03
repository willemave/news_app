//
//  ContentListResponse.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

struct PaginationMetadata: Codable {
    let nextCursor: String?
    let hasMore: Bool
    let pageSize: Int
    let total: Int?

    enum CodingKeys: String, CodingKey {
        case nextCursor = "next_cursor"
        case hasMore = "has_more"
        case pageSize = "page_size"
        case total
    }
}

struct ContentListResponse: Codable {
    let contents: [ContentSummary]
    let availableDates: [String]
    let contentTypes: [String]
    let meta: PaginationMetadata

    enum CodingKeys: String, CodingKey {
        case contents
        case availableDates = "available_dates"
        case contentTypes = "content_types"
        case meta
    }

    var total: Int? { meta.total }
    var nextCursor: String? { meta.nextCursor }
    var hasMore: Bool { meta.hasMore }
    var pageSize: Int { meta.pageSize }
}
