//
//  DetectedFeed.swift
//  newsly
//
//  Created by Claude on 12/20/25.
//

import Foundation

/// A detected RSS/Atom feed from a content page.
struct DetectedFeed: Codable {
    let url: String
    let type: String  // "substack", "podcast_rss", "atom"
    let title: String?
    let format: String  // "rss", "atom"

    /// Human-readable feed type name for display.
    var feedTypeName: String {
        switch type {
        case "substack":
            return "Substack"
        case "podcast_rss":
            return "Podcast"
        case "atom":
            return "RSS Feed"
        default:
            return "Feed"
        }
    }

    /// System icon for the feed type.
    var systemIcon: String {
        switch type {
        case "substack":
            return "envelope.fill"
        case "podcast_rss":
            return "mic.fill"
        case "atom":
            return "dot.radiowaves.left.and.right"
        default:
            return "antenna.radiowaves.left.and.right"
        }
    }
}
