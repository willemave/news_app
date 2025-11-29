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
        provider: ChatModelProvider = .google
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

    func deleteSession(at indexSet: IndexSet) {
        // Note: Backend doesn't support deletion yet, just archive locally
        sessions.remove(atOffsets: indexSet)
    }
}
