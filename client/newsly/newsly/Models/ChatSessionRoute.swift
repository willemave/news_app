//
//  ChatSessionRoute.swift
//  newsly
//
//  Created by Assistant on 12/6/25.
//

import Foundation

struct ChatSessionRoute: Hashable {
    let sessionId: Int
    let contentId: Int?
    let initialUserMessageText: String?
    let initialUserMessageTimestamp: String?
    let pendingMessageId: Int?
    let pendingCouncilPrompt: String?

    init(
        sessionId: Int,
        contentId: Int? = nil,
        initialUserMessageText: String? = nil,
        initialUserMessageTimestamp: String? = nil,
        pendingMessageId: Int? = nil,
        pendingCouncilPrompt: String? = nil
    ) {
        self.sessionId = sessionId
        self.contentId = contentId
        self.initialUserMessageText = initialUserMessageText
        self.initialUserMessageTimestamp = initialUserMessageTimestamp
        self.pendingMessageId = pendingMessageId
        self.pendingCouncilPrompt = pendingCouncilPrompt
    }
}
