//
//  ActiveChatSessionManager.swift
//  newsly
//
//  Created by Assistant on 12/6/25.
//

import Foundation
import SwiftUI
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "ActiveChatSessionManager")

/// Represents an active chat session being polled in the background
struct ActiveChatSession: Identifiable, Equatable {
    let id: Int  // session ID
    let contentId: Int
    let contentTitle: String
    let messageId: Int
    var status: ActiveChatStatus

    enum ActiveChatStatus: Equatable {
        case processing
        case completed
        case failed(String)
    }
}

/// Manager for tracking and polling active chat sessions in the background
@MainActor
class ActiveChatSessionManager: ObservableObject {
    static let shared = ActiveChatSessionManager()

    /// Active sessions being polled, keyed by content ID for quick lookup
    @Published private(set) var activeSessions: [Int: ActiveChatSession] = [:]  // contentId -> session

    /// Completed sessions that haven't been viewed yet
    @Published private(set) var completedSessions: [Int: ActiveChatSession] = [:]  // contentId -> session

    private let chatService = ChatService.shared
    private let notificationService = LocalNotificationService.shared

    /// Polling interval (500ms)
    private let pollingInterval: UInt64 = 500_000_000

    /// Maximum polling attempts (120 = 60 seconds)
    private let maxPollingAttempts = 120

    private var pollingTasks: [Int: Task<Void, Never>] = [:]  // contentId -> task

    private init() {}

    /// Start tracking a new chat session
    func startTracking(
        session: ChatSessionSummary,
        contentId: Int,
        contentTitle: String,
        messageId: Int
    ) {
        let activeSession = ActiveChatSession(
            id: session.id,
            contentId: contentId,
            contentTitle: contentTitle,
            messageId: messageId,
            status: .processing
        )

        activeSessions[contentId] = activeSession
        logger.info("Started tracking session \(session.id) for content \(contentId)")

        // Start background polling
        let task = Task {
            await pollForCompletion(contentId: contentId, messageId: messageId)
        }
        pollingTasks[contentId] = task
    }

    /// Stop tracking a session (e.g., when user opens the chat view)
    func stopTracking(contentId: Int) {
        pollingTasks[contentId]?.cancel()
        pollingTasks.removeValue(forKey: contentId)
        activeSessions.removeValue(forKey: contentId)
        completedSessions.removeValue(forKey: contentId)
        logger.info("Stopped tracking for content \(contentId)")
    }

    /// Mark a completed session as viewed (dismisses banner)
    func markAsViewed(contentId: Int) {
        completedSessions.removeValue(forKey: contentId)
    }

    /// Get active session for a content ID if any
    func getSession(forContentId contentId: Int) -> ActiveChatSession? {
        return activeSessions[contentId] ?? completedSessions[contentId]
    }

    /// Check if there's an active or completed session for this content
    func hasActiveSession(forContentId contentId: Int) -> Bool {
        return activeSessions[contentId] != nil || completedSessions[contentId] != nil
    }

    /// Poll for message completion
    private func pollForCompletion(contentId: Int, messageId: Int) async {
        var attempts = 0

        while attempts < maxPollingAttempts {
            do {
                try Task.checkCancellation()

                let status = try await chatService.getMessageStatus(messageId: messageId)

                switch status.status {
                case .completed:
                    await handleCompletion(contentId: contentId, success: true)
                    return

                case .failed:
                    let errorMsg = status.error ?? "Unknown error"
                    await handleFailure(contentId: contentId, error: errorMsg)
                    return

                case .processing:
                    attempts += 1
                    try await Task.sleep(nanoseconds: pollingInterval)
                }
            } catch is CancellationError {
                logger.info("Polling cancelled for content \(contentId)")
                return
            } catch {
                logger.error("Polling error for content \(contentId): \(error.localizedDescription)")
                await handleFailure(contentId: contentId, error: error.localizedDescription)
                return
            }
        }

        // Timeout
        await handleFailure(contentId: contentId, error: "Request timed out")
    }

    private func handleCompletion(contentId: Int, success: Bool) async {
        guard var session = activeSessions[contentId] else { return }

        session.status = .completed
        activeSessions.removeValue(forKey: contentId)
        completedSessions[contentId] = session
        pollingTasks.removeValue(forKey: contentId)

        logger.info("Chat completed for content \(contentId)")

        // Show local notification
        notificationService.showChatCompletedNotification(
            sessionId: session.id,
            title: "Chat Ready",
            message: "Your analysis of \"\(session.contentTitle)\" is ready"
        )
    }

    private func handleFailure(contentId: Int, error: String) async {
        guard var session = activeSessions[contentId] else { return }

        session.status = .failed(error)
        activeSessions.removeValue(forKey: contentId)
        completedSessions[contentId] = session
        pollingTasks.removeValue(forKey: contentId)

        logger.error("Chat failed for content \(contentId): \(error)")
    }
}
