//
//  NewsGroupViewModel.swift
//  newsly
//
//  Created by Assistant on 10/12/25.
//

import Foundation
import SwiftUI

@MainActor
class NewsGroupViewModel: ObservableObject {
    @Published var newsGroups: [NewsGroup] = []
    @Published var isLoading = false
    @Published var isLoadingMore = false
    @Published var errorMessage: String?

    // Pagination state
    @Published var nextCursor: String?
    @Published var hasMore: Bool = false

    private let contentService = ContentService.shared
    private let unreadCountService = UnreadCountService.shared

    func loadNewsGroups() async {
        isLoading = true
        errorMessage = nil
        nextCursor = nil
        hasMore = false

        do {
            // Load news content (limit 30 to get 5 groups of 6)
            let response = try await contentService.fetchContentList(
                contentType: "news",
                date: nil,
                readFilter: "unread",
                cursor: nil,
                limit: 30
            )

            // Group items by 6
            newsGroups = response.contents.groupedBySix()
            nextCursor = response.nextCursor
            hasMore = response.hasMore
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func loadMoreGroups() async {
        guard !isLoadingMore, !isLoading, hasMore, let cursor = nextCursor else {
            return
        }

        isLoadingMore = true

        do {
            let response = try await contentService.fetchContentList(
                contentType: "news",
                date: nil,
                readFilter: "unread",
                cursor: cursor,
                limit: 30
            )

            // Append new groups
            let newGroups = response.contents.groupedBySix()
            newsGroups.append(contentsOf: newGroups)
            nextCursor = response.nextCursor
            hasMore = response.hasMore
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoadingMore = false
    }

    func markGroupAsRead(_ groupId: String) async {
        guard let groupIndex = newsGroups.firstIndex(where: { $0.id == groupId }) else {
            return
        }

        let group = newsGroups[groupIndex]
        let itemIds = group.items.map { $0.id }

        do {
            _ = try await contentService.bulkMarkAsRead(contentIds: itemIds)

            // Update local state to mark as read (CardStackView filters these out)
            newsGroups[groupIndex] = group.updatingAllAsRead(true)

            // Update unread counts
            unreadCountService.decrementNewsCount(by: itemIds.count)

            // NOTE: We no longer remove from array here
            // CardStackView filters out read groups using dismissed set + isRead flag
            // This keeps the array stable and prevents index/array desynchronization
        } catch {
            ToastService.shared.showError("Failed to mark as read")
            errorMessage = "Failed to mark group as read: \(error.localizedDescription)"
        }
    }

    func preloadNextGroups() async {
        // Trigger load when down to 2 unread groups
        let unreadCount = newsGroups.filter { !$0.isRead }.count
        if unreadCount <= 2 && !isLoadingMore && hasMore {
            await loadMoreGroups()
        }
    }

    func toggleFavorite(_ contentId: Int) async {
        // Find group and item
        guard let groupIndex = newsGroups.firstIndex(where: { $0.items.contains(where: { $0.id == contentId }) }) else {
            return
        }

        let group = newsGroups[groupIndex]
        guard group.items.contains(where: { $0.id == contentId }) else {
            return
        }

        // Optimistically update
        newsGroups[groupIndex] = group.updatingItem(id: contentId) { item in
            item.updating(isFavorited: !item.isFavorited)
        }

        do {
            let response = try await contentService.toggleFavorite(id: contentId)

            // Update with server response
            if let isFavorited = response["is_favorited"] as? Bool {
                newsGroups[groupIndex] = group.updatingItem(id: contentId) { item in
                    item.updating(isFavorited: isFavorited)
                }
            }
        } catch {
            // Revert on error
            newsGroups[groupIndex] = group.updatingItem(id: contentId) { item in
                item.updating(isFavorited: !item.isFavorited)
            }
            errorMessage = "Failed to toggle favorite"
        }
    }

    func convertToArticle(_ contentId: Int) async {
        do {
            let response = try await contentService.convertNewsToArticle(id: contentId)

            // Show success message or navigate to new article
            // For now, just log success
            print("Converted to article: \(response.newContentId), already exists: \(response.alreadyExists)")

            // Optionally: Navigate to the article detail view
            // or show a toast notification
        } catch {
            errorMessage = "Failed to convert: \(error.localizedDescription)"
        }
    }

    func refresh() async {
        nextCursor = nil
        hasMore = false
        await loadNewsGroups()

        // Clean up read groups on refresh to prevent array bloat
        // Keep the array fresh with only unread items
        newsGroups = newsGroups.filter { !$0.isRead }
    }
}
