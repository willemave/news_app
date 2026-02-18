//
//  ContentDiscussion.swift
//  newsly
//
//  Created by Assistant on 2/18/26.
//

import Foundation

struct ContentDiscussion: Codable {
    let contentId: Int
    let status: String
    let mode: String
    let platform: String?
    let sourceURL: String?
    let discussionURL: String?
    let fetchedAt: String?
    let errorMessage: String?
    let comments: [DiscussionComment]
    let discussionGroups: [DiscussionGroup]
    let links: [DiscussionLink]
    let stats: [String: AnyCodable]

    enum CodingKeys: String, CodingKey {
        case contentId = "content_id"
        case status
        case mode
        case platform
        case sourceURL = "source_url"
        case discussionURL = "discussion_url"
        case fetchedAt = "fetched_at"
        case errorMessage = "error_message"
        case comments
        case discussionGroups = "discussion_groups"
        case links
        case stats
    }

    var hasRenderableContent: Bool {
        if mode == "comments" {
            return !comments.isEmpty || !links.isEmpty
        }
        if mode == "discussion_list" {
            return !discussionGroups.isEmpty
        }
        return false
    }
}

struct DiscussionComment: Codable, Identifiable {
    let commentID: String
    let parentID: String?
    let author: String?
    let text: String
    let compactText: String?
    let depth: Int
    let createdAt: String?
    let sourceURL: String?

    enum CodingKeys: String, CodingKey {
        case commentID = "comment_id"
        case parentID = "parent_id"
        case author
        case text
        case compactText = "compact_text"
        case depth
        case createdAt = "created_at"
        case sourceURL = "source_url"
    }

    var id: String { commentID }
}

struct DiscussionGroup: Codable, Identifiable {
    let label: String
    let items: [DiscussionItem]

    var id: String { label }
}

struct DiscussionItem: Codable, Identifiable {
    let title: String
    let url: String

    var id: String { url }
}

struct DiscussionLink: Codable, Identifiable {
    let url: String
    let source: String
    let commentID: String?
    let groupLabel: String?
    let title: String?

    enum CodingKeys: String, CodingKey {
        case url
        case source
        case commentID = "comment_id"
        case groupLabel = "group_label"
        case title
    }

    var id: String { url }
}
