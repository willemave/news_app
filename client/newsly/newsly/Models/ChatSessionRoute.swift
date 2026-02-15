//
//  ChatSessionRoute.swift
//  newsly
//
//  Created by Assistant on 12/6/25.
//

import Foundation

enum ChatSessionRouteMode: String, Hashable {
    case text
    case live
}

struct ChatSessionRoute: Hashable {
    let sessionId: Int
    let mode: ChatSessionRouteMode
    let contentId: Int?

    init(sessionId: Int, mode: ChatSessionRouteMode = .text, contentId: Int? = nil) {
        self.sessionId = sessionId
        self.mode = mode
        self.contentId = contentId
    }
}
