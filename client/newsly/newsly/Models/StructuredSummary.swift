//
//  StructuredSummary.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

struct StructuredSummary: Codable {
    let title: String?
    let overview: String?
    let bulletPoints: [BulletPoint]
    let quotes: [Quote]
    let topics: [String]
    let questions: [String]?
    let counterArguments: [String]?
    let summarizationDate: String?
    let classification: String?

    enum CodingKeys: String, CodingKey {
        case title
        case overview
        case bulletPoints = "bullet_points"
        case quotes
        case topics
        case questions
        case counterArguments = "counter_arguments"
        case summarizationDate = "summarization_date"
        case classification
    }
}

struct BulletPoint: Codable {
    let text: String
    let category: String?
}

struct Quote: Codable {
    let text: String
    let context: String?
}

// MARK: - Interleaved Summary Format

struct InterleavedInsight: Codable, Identifiable {
    let topic: String
    let insight: String
    let supportingQuote: String?
    let quoteAttribution: String?

    var id: String { topic + insight.prefix(20) }

    enum CodingKeys: String, CodingKey {
        case topic
        case insight
        case supportingQuote = "supporting_quote"
        case quoteAttribution = "quote_attribution"
    }
}

struct InterleavedSummary: Codable {
    let summaryType: String?
    let title: String?
    let hook: String
    let insights: [InterleavedInsight]
    let takeaway: String
    let classification: String?
    let summarizationDate: String?

    enum CodingKeys: String, CodingKey {
        case summaryType = "summary_type"
        case title
        case hook
        case insights
        case takeaway
        case classification
        case summarizationDate = "summarization_date"
    }
}