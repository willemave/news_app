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
    @Published var errorMessage: String?
    
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
        
        do {
            let response = try await contentService.fetchContentList(
                contentType: selectedContentType,
                date: selectedDate.isEmpty ? nil : selectedDate,
                readFilter: selectedReadFilter
            )
            
            contents = response.contents
            availableDates = response.availableDates
            contentTypes = response.contentTypes
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
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
                    _ = withAnimation(.easeOut(duration: 0.3)) {
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
                _ = withAnimation(.easeOut(duration: 0.3)) {
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
        
        do {
            let response = try await contentService.fetchFavoritesList()
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
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func refresh() async {
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
                _ = withAnimation(.easeOut(duration: 0.3)) {
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
