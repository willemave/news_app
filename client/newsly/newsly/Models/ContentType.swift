//
//  ContentType.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

enum ContentType: String, Codable, CaseIterable {
    case article = "article"
    case podcast = "podcast"
    case news = "news"
    
    var displayName: String {
        switch self {
        case .article:
            return "Article"
        case .podcast:
            return "Podcast"
        case .news:
            return "News"
        }
    }
}
