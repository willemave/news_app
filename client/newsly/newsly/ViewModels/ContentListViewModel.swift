//
//  ContentListViewModel.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation
import SwiftUI

@MainActor
class ContentListViewModel: ObservableObject {
    @Published var contents: [ContentSummary] = []
    @Published var availableDates: [String] = []
    @Published var contentTypes: [String] = []
    @Published var isLoading = false
    @Published var isLoadingMore = false
    @Published var errorMessage: String?

    // Pagination state
    @Published var nextCursor: String?
    @Published var hasMore: Bool = false

    // Track if we're in favorites mode
    private var isFavoritesMode: Bool = false
    // Track if we're in recently read mode
    private var isRecentlyReadMode: Bool = false

    @Published var selectedContentType: String = "all" {
        didSet {
            Task { await loadContent() }
        }
    }
    @Published var selectedDate: String = "" {
        didSet {
            Task { await loadContent() }
        }
    }
    @Published var selectedReadFilter: String = "unread" {
        didSet {
            Task { await loadContent() }
        }
    }

    private let contentService = ContentService.shared
    private let unreadCountService = UnreadCountService.shared
    
    func loadContent() async {
        isLoading = true
        errorMessage = nil

        // Reset pagination and special modes when loading fresh content
        isFavoritesMode = false
        isRecentlyReadMode = false
        nextCursor = nil
        hasMore = false

        do {
            let response = try await contentService.fetchContentList(
                contentType: selectedContentType,
                date: selectedDate.isEmpty ? nil : selectedDate,
                readFilter: selectedReadFilter,
                cursor: nil  // Always start from beginning
            )

            contents = response.contents
            availableDates = response.availableDates
            contentTypes = response.contentTypes
            nextCursor = response.nextCursor
            hasMore = response.hasMore
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func loadMoreContent() async {
        // Don't load more if already loading or no more content
        guard !isLoadingMore, !isLoading, hasMore, let cursor = nextCursor else {
            return
        }

        isLoadingMore = true

        do {
            let response: ContentListResponse

            if isFavoritesMode {
                response = try await contentService.fetchFavoritesList(cursor: cursor)
            } else if isRecentlyReadMode {
                response = try await contentService.fetchRecentlyReadList(cursor: cursor)
            } else {
                response = try await contentService.fetchContentList(
                    contentType: selectedContentType,
                    date: selectedDate.isEmpty ? nil : selectedDate,
                    readFilter: selectedReadFilter,
                    cursor: cursor
                )
            }

            // Append new contents to existing list
            var items = response.contents

            // Apply read filter locally for favorites only (not recently read - all items are read by definition)
            if isFavoritesMode {
                switch selectedReadFilter {
                case "unread":
                    items = items.filter { !$0.isRead }
                case "read":
                    items = items.filter { $0.isRead }
                default:
                    break
                }
            }

            contents.append(contentsOf: items)
            nextCursor = response.nextCursor
            hasMore = response.hasMore
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoadingMore = false
    }
    
    func markAsRead(_ contentId: Int) async {
        do {
            try await contentService.markContentAsRead(id: contentId)

            if let index = contents.firstIndex(where: { $0.id == contentId }) {
                let current = contents[index]
                contents[index] = current.updating(isRead: true)

                switch current.contentType {
                case "article":
                    unreadCountService.decrementArticleCount()
                case "podcast":
                    unreadCountService.decrementPodcastCount()
                case "news":
                    unreadCountService.decrementNewsCount()
                default:
                    break
                }

                if selectedReadFilter == "unread" {
                    withAnimation(.easeOut(duration: 0.3)) {
                        contents.remove(at: index)
                    }
                }
            }
        } catch {
            errorMessage = "Failed to mark as read: \(error.localizedDescription)"
        }
    }
    
    func toggleFavorite(_ contentId: Int) async {
        do {
            // Find the content
            guard let index = contents.firstIndex(where: { $0.id == contentId }) else { return }
            let currentContent = contents[index]
            
            // Optimistically update the UI
            contents[index] = currentContent.updating(isFavorited: !currentContent.isFavorited)
            
            // Make API call
            let response = try await contentService.toggleFavorite(id: contentId)
            
            // Update with server response
            if let isFavorited = response["is_favorited"] as? Bool {
                contents[index] = currentContent.updating(isFavorited: isFavorited)
            }
        } catch {
            // Revert on error
            if let index = contents.firstIndex(where: { $0.id == contentId }) {
                contents[index] = contents[index].updating(isFavorited: !contents[index].isFavorited)
            }
            errorMessage = "Failed to update favorite status"
        }
    }
    
    func toggleUnlike(_ contentId: Int) async {
        do {
            // Find the content
            guard let index = contents.firstIndex(where: { $0.id == contentId }) else { return }
            let currentContent = contents[index]

            // Optimistically update the UI
            var updatedContent = currentContent.updating(isUnliked: !currentContent.isUnliked)
            if updatedContent.isUnliked {
                if !updatedContent.isRead {
                    updatedContent = updatedContent.updating(isRead: true, isUnliked: true)

                    switch updatedContent.contentType {
                    case "article":
                        unreadCountService.decrementArticleCount()
                    case "podcast":
                        unreadCountService.decrementPodcastCount()
                    case "news":
                        unreadCountService.decrementNewsCount()
                    default:
                        break
                    }
                }
            }

            contents[index] = updatedContent

            // Make API call
            let response = try await contentService.toggleUnlike(id: contentId)

            // Update with server response
            let isUnliked = (response["is_unliked"] as? Bool) ?? updatedContent.isUnliked
            let isRead = (response["is_read"] as? Bool) ?? updatedContent.isRead

            var finalContent = updatedContent.updating(isUnliked: isUnliked)
            if isRead {
                finalContent = finalContent.updating(isRead: true)
            }

            if selectedReadFilter == "unread" && isRead {
                // Remove from list when filtering by unread
                withAnimation(.easeOut(duration: 0.3)) {
                    contents.remove(at: index)
                }
            } else {
                contents[index] = finalContent
            }
        } catch {
            // Revert on error
            if let idx = contents.firstIndex(where: { $0.id == contentId }) {
                contents[idx] = contents[idx].updating(isUnliked: !contents[idx].isUnliked)
            }
            errorMessage = "Failed to update unlike status"
        }
    }
    
    func loadFavorites() async {
        isLoading = true
        errorMessage = nil

        // Set favorites mode and reset pagination
        isFavoritesMode = true
        isRecentlyReadMode = false
        nextCursor = nil
        hasMore = false

        do {
            let response = try await contentService.fetchFavoritesList(cursor: nil)
            var items = response.contents
            // Apply read filter locally for favorites
            switch selectedReadFilter {
            case "unread":
                items = items.filter { !$0.isRead }
            case "read":
                items = items.filter { $0.isRead }
            default:
                break
            }
            contents = items
            availableDates = response.availableDates
            contentTypes = response.contentTypes
            nextCursor = response.nextCursor
            hasMore = response.hasMore
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func loadRecentlyRead() async {
        isLoading = true
        errorMessage = nil

        // Set recently read mode and reset pagination
        isFavoritesMode = false
        isRecentlyReadMode = true
        nextCursor = nil
        hasMore = false

        do {
            let response = try await contentService.fetchRecentlyReadList(cursor: nil)
            // Don't apply read filter for recently read - all items are already read by definition
            contents = response.contents
            availableDates = response.availableDates
            contentTypes = response.contentTypes
            nextCursor = response.nextCursor
            hasMore = response.hasMore
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func refresh() async {
        // Reset pagination and reload
        nextCursor = nil
        hasMore = false
        await loadContent()
    }

    func markAllAsRead() async {
        let unreadIds = contents.filter { !$0.isRead }.map { $0.id }
        if unreadIds.isEmpty {
            return
        }

        do {
            let response = try await contentService.bulkMarkAsRead(contentIds: unreadIds)
            let markedSet = Set(unreadIds)

            contents = contents.map { item in
                if markedSet.contains(item.id) {
                    return item.updating(isRead: true)
                }
                return item
            }

            if selectedReadFilter == "unread" {
                withAnimation(.easeOut(duration: 0.3)) {
                    contents.removeAll { markedSet.contains($0.id) }
                }
            }

            if response.markedCount > 0 {
                switch selectedContentType {
                case "article":
                    unreadCountService.decrementArticleCount(by: response.markedCount)
                case "podcast":
                    unreadCountService.decrementPodcastCount(by: response.markedCount)
                case "news":
                    unreadCountService.decrementNewsCount(by: response.markedCount)
                default:
                    break
                }
            }
        } catch {
            errorMessage = "Failed to mark all as read: \(error.localizedDescription)"
        }
    }
}
