//
//  Narration.swift
//  newsly
//

import Foundation

enum NarrationTarget: Hashable {
    case content(Int)

    var id: Int {
        switch self {
        case .content(let id):
            return id
        }
    }

    var pathComponent: String {
        switch self {
        case .content:
            return "content"
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
