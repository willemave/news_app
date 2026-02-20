//
//  DiscoverySuggestion.swift
//  newsly
//

import Foundation

struct DiscoverySuggestion: Codable, Identifiable {
    let id: Int
    let suggestionType: String
    let siteURL: String?
    let feedURL: String
    let itemURL: String?
    let title: String?
    let description: String?
    let channelId: String?
    let playlistId: String?
    let rationale: String?
    let score: Double?
    let status: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case suggestionType = "suggestion_type"
        case siteURL = "site_url"
        case feedURL = "feed_url"
        case itemURL = "item_url"
        case title
        case description
        case channelId = "channel_id"
        case playlistId = "playlist_id"
        case rationale
        case score
        case status
        case createdAt = "created_at"
    }
}

struct DiscoverySuggestionsResponse: Codable {
    let runId: Int?
    let runStatus: String?
    let runCreatedAt: String?
    let directionSummary: String?
    let feeds: [DiscoverySuggestion]
    let podcasts: [DiscoverySuggestion]
    let youtube: [DiscoverySuggestion]

    enum CodingKeys: String, CodingKey {
        case runId = "run_id"
        case runStatus = "run_status"
        case runCreatedAt = "run_created_at"
        case directionSummary = "direction_summary"
        case feeds
        case podcasts
        case youtube
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        runId = try container.decodeIfPresent(Int.self, forKey: .runId)
        runStatus = try container.decodeIfPresent(String.self, forKey: .runStatus)
        runCreatedAt = try container.decodeIfPresent(String.self, forKey: .runCreatedAt)
        directionSummary = try container.decodeIfPresent(String.self, forKey: .directionSummary)
        feeds = try container.decodeIfPresent([DiscoverySuggestion].self, forKey: .feeds) ?? []
        podcasts = try container.decodeIfPresent([DiscoverySuggestion].self, forKey: .podcasts) ?? []
        youtube = try container.decodeIfPresent([DiscoverySuggestion].self, forKey: .youtube) ?? []
    }
}

struct DiscoveryRunSuggestions: Codable, Identifiable {
    let runId: Int
    let runStatus: String
    let runCreatedAt: String
    let directionSummary: String?
    let feeds: [DiscoverySuggestion]
    let podcasts: [DiscoverySuggestion]
    let youtube: [DiscoverySuggestion]

    var id: Int { runId }

    enum CodingKeys: String, CodingKey {
        case runId = "run_id"
        case runStatus = "run_status"
        case runCreatedAt = "run_created_at"
        case directionSummary = "direction_summary"
        case feeds
        case podcasts
        case youtube
    }
}

struct DiscoveryHistoryResponse: Codable {
    let runs: [DiscoveryRunSuggestions]
}

struct DiscoveryRefreshResponse: Codable {
    let status: String
    let taskId: Int?

    enum CodingKeys: String, CodingKey {
        case status
        case taskId = "task_id"
    }
}

struct DiscoveryActionError: Codable {
    let id: String
    let error: String
}

struct DiscoverySubscribeResponse: Codable {
    let subscribed: [Int]
    let skipped: [Int]
    let errors: [DiscoveryActionError]
}

struct DiscoveryAddItemResponse: Codable {
    let created: [Int]
    let skipped: [Int]
    let errors: [DiscoveryActionError]
}

struct DiscoveryDismissResponse: Codable {
    let dismissed: [Int]
}

struct DiscoveryPodcastSearchResult: Codable, Identifiable {
    let title: String
    let episodeURL: String
    let podcastTitle: String?
    let source: String?
    let snippet: String?
    let feedURL: String?
    let publishedAt: String?
    let provider: String?
    let score: Double?

    var id: String { episodeURL }

    enum CodingKeys: String, CodingKey {
        case title
        case episodeURL = "episode_url"
        case podcastTitle = "podcast_title"
        case source
        case snippet
        case feedURL = "feed_url"
        case publishedAt = "published_at"
        case provider
        case score
    }
}

struct DiscoveryPodcastSearchResponse: Codable {
    let results: [DiscoveryPodcastSearchResult]
}

extension DiscoverySuggestion {
    var displayTitle: String {
        if let title, !title.isEmpty {
            return title
        }
        if let siteURL, !siteURL.isEmpty {
            return siteURL
        }
        return feedURL
    }

    var displaySubtitle: String? {
        if let description, !description.isEmpty {
            return description
        }
        if let rationale, !rationale.isEmpty {
            return rationale
        }
        return nil
    }

    var primaryURL: String {
        siteURL ?? feedURL
    }

    var hasItem: Bool {
        itemURL != nil
    }

    var canSubscribe: Bool {
        if suggestionType == "youtube" {
            if channelId != nil || playlistId != nil {
                return true
            }
            let lower = feedURL.lowercased()
            return !lower.contains("youtube.com/watch") && !lower.contains("youtu.be/")
        }
        if suggestionType == "podcast_rss" {
            return itemURL == nil
        }
        return true
    }

    var subscribeLabel: String {
        return "Subscribe"
    }

    var addItemLabel: String {
        if suggestionType == "youtube" {
            return "Add Video"
        }
        if suggestionType == "podcast_rss" {
            return "Add Episode"
        }
        return "Add Item"
    }
}
