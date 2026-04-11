//
//  KnowledgeHubViewModel.swift
//  newsly
//

import Foundation
import SwiftUI

@MainActor
protocol KnowledgeHubChatServicing: AnyObject {
    func listSessions(contentId: Int?, limit: Int) async throws -> [ChatSessionSummary]

    func createAssistantTurn(
        message: String,
        sessionId: Int?,
        screenContext: AssistantScreenContext
    ) async throws -> AssistantTurnResponse

    func createSession(
        contentId: Int?,
        topic: String?,
        provider: ChatModelProvider?,
        modelHint: String?,
        initialMessage: String?
    ) async throws -> ChatSessionSummary
}

extension ChatService: KnowledgeHubChatServicing {}

@MainActor
class KnowledgeHubViewModel: ObservableObject {
    @Published var recentSessions: [ChatSessionSummary] = []
    @Published var isLoading = false
    @Published var isCreatingSession = false
    @Published var errorMessage: String?

    private let chatService: any KnowledgeHubChatServicing

    init(chatService: any KnowledgeHubChatServicing = ChatService.shared) {
        self.chatService = chatService
    }

    func loadHub() async {
        isLoading = true
        errorMessage = nil

        do {
            let sessions = try await chatService.listSessions(contentId: nil, limit: 10)
            recentSessions = Array(sessions.prefix(5))
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func startNewChat() async -> ChatSessionRoute? {
        guard !isCreatingSession else { return nil }
        isCreatingSession = true
        errorMessage = nil
        defer { isCreatingSession = false }

        do {
            let session = try await chatService.createSession(
                contentId: nil, topic: nil, provider: nil,
                modelHint: nil, initialMessage: nil
            )
            return ChatSessionRoute(sessionId: session.id)
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    func startSearchChat(message: String) async -> ChatSessionRoute? {
        await startHubAssistantTurn(message: message)
    }

    func startSummaryChat() async -> ChatSessionRoute? {
        await startHubAssistantTurn(
            message: (
                "Give me a summary of the last day's content from my feed, "
                + "including recent news items and articles. "
                + "What are the key themes and most important takeaways?"
            ),
            screenContext: makeHubContext(
                query: "recent news items and articles from my feed",
                note: (
                    "Summarize recent in-app feed content. Include both short-form news "
                    + "items and longer articles. Prefer in-app content before web search."
                )
            )
        )
    }

    func startCommentsChat() async -> ChatSessionRoute? {
        await startHubAssistantTurn(
            message: (
                "What are the most interesting and insightful comments from the "
                + "news items and articles in my feed recently? "
                + "Highlight any surprising perspectives or debates."
            )
        )
    }

    func startFindArticlesChat() async -> ChatSessionRoute? {
        await startHubAssistantTurn(
            message: "Find a few new articles or sources I should read next based on what I've been reading."
        )
    }

    func startFindFeedsChat() async -> ChatSessionRoute? {
        await startHubAssistantTurn(
            message: "Recommend a few feeds, newsletters, or podcasts I should add based on what I've been reading."
        )
    }

    private func startHubAssistantTurn(
        message: String,
        screenContext: AssistantScreenContext? = nil
    ) async -> ChatSessionRoute? {
        guard !isCreatingSession else { return nil }
        isCreatingSession = true
        errorMessage = nil
        defer { isCreatingSession = false }

        do {
            let response = try await chatService.createAssistantTurn(
                message: message,
                sessionId: nil,
                screenContext: screenContext ?? makeHubContext()
            )
            return ChatSessionRoute(
                sessionId: response.session.id,
                initialUserMessageText: response.userMessage.content,
                initialUserMessageTimestamp: response.userMessage.timestamp,
                pendingMessageId: response.messageId
            )
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    private func makeHubContext(
        query: String? = nil,
        note: String? = nil
    ) -> AssistantScreenContext {
        AssistantScreenContext(
            screenType: "knowledge_hub",
            screenTitle: "Knowledge",
            query: query,
            note: note
        )
    }
}
