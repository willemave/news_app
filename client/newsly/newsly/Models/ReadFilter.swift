//
//  ReadFilter.swift
//  newsly
//
//  Created by Assistant on 3/16/26.
//

import Foundation

enum ReadFilter: String, Codable, CaseIterable {
    case all
    case read
    case unread
}
