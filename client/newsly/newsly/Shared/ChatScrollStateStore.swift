//
//  ChatScrollStateStore.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "ChatScrollState")

struct ChatScrollState: Codable, Equatable {
    let sessionId: Int
    let anchorMessageId: Int?
    let wasAtBottom: Bool
    let updatedAt: Date
}

enum ChatScrollStateStore {
    private static let storagePrefix = "chatScrollState:"

    static func load(sessionId: Int) -> ChatScrollState? {
        let key = storageKey(for: sessionId)
        guard let data = UserDefaults.standard.data(forKey: key) else { return nil }

        do {
            return try JSONDecoder().decode(ChatScrollState.self, from: data)
        } catch {
            logger.error("[ChatScrollState] decode failed | sessionId=\(sessionId) error=\(error.localizedDescription)")
            return nil
        }
    }

    static func save(sessionId: Int, anchorMessageId: Int?, wasAtBottom: Bool) {
        let state = ChatScrollState(
            sessionId: sessionId,
            anchorMessageId: anchorMessageId,
            wasAtBottom: wasAtBottom,
            updatedAt: Date()
        )

        do {
            let data = try JSONEncoder().encode(state)
            UserDefaults.standard.set(data, forKey: storageKey(for: sessionId))
        } catch {
            logger.error("[ChatScrollState] encode failed | sessionId=\(sessionId) error=\(error.localizedDescription)")
        }
    }

    static func clear(sessionId: Int) {
        UserDefaults.standard.removeObject(forKey: storageKey(for: sessionId))
    }

    private static func storageKey(for sessionId: Int) -> String {
        "\(storagePrefix)\(sessionId)"
    }
}
