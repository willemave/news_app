//
//  LiveVoiceRoute.swift
//  newsly
//

import Foundation

enum LiveLaunchMode: String, Codable, Hashable {
    case general
    case articleVoice = "article_voice"
    case dictateSummary = "dictate_summary"
}

enum LiveVoiceSourceSurface: String, Codable, Hashable {
    case knowledgeLive = "knowledge_live"
    case chatSession = "chat_session"
    case contentDetail = "content_detail"
}

struct LiveVoiceRoute: Hashable, Codable {
    let sessionId: String?
    let chatSessionId: Int?
    let contentId: Int?
    let launchMode: LiveLaunchMode
    let sourceSurface: LiveVoiceSourceSurface
    let autoConnect: Bool

    init(
        sessionId: String? = nil,
        chatSessionId: Int? = nil,
        contentId: Int? = nil,
        launchMode: LiveLaunchMode = .general,
        sourceSurface: LiveVoiceSourceSurface = .knowledgeLive,
        autoConnect: Bool = true
    ) {
        self.sessionId = sessionId
        self.chatSessionId = chatSessionId
        self.contentId = contentId
        self.launchMode = launchMode
        self.sourceSurface = sourceSurface
        self.autoConnect = autoConnect
    }
}
