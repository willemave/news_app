//
//  ContentDetailRoute.swift
//  newsly
//
//  Created by Assistant on 3/16/26.
//

import Foundation

struct ContentDetailRoute: Hashable, Codable {
    let contentId: Int
    let contentType: ContentType
    let allContentIds: [Int]

    init(contentId: Int, contentType: ContentType, allContentIds: [Int]) {
        self.contentId = contentId
        self.contentType = contentType
        self.allContentIds = allContentIds
    }

    init(summary: ContentSummary, allContentIds: [Int]) {
        self.contentId = summary.id
        self.contentType = summary.contentTypeEnum ?? .article
        self.allContentIds = allContentIds
    }
}
