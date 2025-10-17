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