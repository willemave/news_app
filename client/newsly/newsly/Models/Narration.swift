//
//  Narration.swift
//  newsly
//

import Foundation

enum NarrationTarget: Hashable {
    case content(Int)
    case dailyDigest(Int)

    var id: Int {
        switch self {
        case .content(let id), .dailyDigest(let id):
            return id
        }
    }

    var pathComponent: String {
        switch self {
        case .content:
            return "content"
        case .dailyDigest:
            return "daily-digest"
        }
    }
}

struct NarrationResponse: Codable {
    let targetType: String
    let targetId: Int
    let title: String
    let narrationText: String

    enum CodingKeys: String, CodingKey {
        case targetType = "target_type"
        case targetId = "target_id"
        case title
        case narrationText = "narration_text"
    }
}
