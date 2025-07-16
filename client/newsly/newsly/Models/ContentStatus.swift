//
//  ContentStatus.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

enum ContentStatus: String, Codable {
    case new = "new"
    case processing = "processing"
    case completed = "completed"
    case failed = "failed"
    case skipped = "skipped"
    
    var displayName: String {
        return self.rawValue.capitalized
    }
}