//
//  ChatSessionsViewModel.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import Foundation
import SwiftUI

@MainActor
class ChatSessionsViewModel: ObservableObject {
    @Published var sessions: [ChatSessionSummary] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let chatService = ChatService.shared

    func loadSessions() async {
        isLoading = true
        errorMessage = nil

        do {
            sessions = try await chatService.listSessions()
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func createSession(
        contentId: Int? = nil,
        topic: String? = nil,
        provider: ChatModelProvider = .anthropic
    ) async -> ChatSessionSummary? {
        do {
            let session = try await chatService.createSession(
                contentId: contentId,
                topic: topic,
                provider: provider
            )
            // Prepend to list
            sessions.insert(session, at: 0)
            return session
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    func deleteSessions(ids: [Int]) async {
        guard !ids.isEmpty else { return }

        errorMessage = nil
        let previousSessions = sessions
        sessions.removeAll { ids.contains($0.id) }

        do {
            for id in ids {
                try await chatService.deleteSession(sessionId: id)
            }
        } catch {
            sessions = previousSessions
            errorMessage = error.localizedDescription
            await loadSessions()
        }
    }
}
