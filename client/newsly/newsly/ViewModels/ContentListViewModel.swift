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
            
            // Update local state to reflect the change
            if let index = contents.firstIndex(where: { $0.id == contentId }) {
                let updatedContent = contents[index]
                // Create a new instance with updated isRead status
                let newContent = ContentSummary(
                    id: updatedContent.id,
                    contentType: updatedContent.contentType,
                    url: updatedContent.url,
                    title: updatedContent.title,
                    source: updatedContent.source,
                    platform: updatedContent.platform,
                    status: updatedContent.status,
                    shortSummary: updatedContent.shortSummary,
                    createdAt: updatedContent.createdAt,
                    processedAt: updatedContent.processedAt,
                    classification: updatedContent.classification,
                    publicationDate: updatedContent.publicationDate,
                    isRead: true,
                    isFavorited: updatedContent.isFavorited,
                    isUnliked: updatedContent.isUnliked
                )
                contents[index] = newContent
                
                // Update unread count based on content type
                if updatedContent.contentType == "article" {
                    unreadCountService.decrementArticleCount()
                } else if updatedContent.contentType == "podcast" {
                    unreadCountService.decrementPodcastCount()
                }
                
                // If filtering by unread, remove from list with animation
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
            var updatedContent = currentContent
            updatedContent.isFavorited.toggle()
            contents[index] = updatedContent
            
            // Make API call
            let response = try await contentService.toggleFavorite(id: contentId)
            
            // Update with server response
            if let isFavorited = response["is_favorited"] as? Bool {
                var finalContent = currentContent
                finalContent.isFavorited = isFavorited
                contents[index] = finalContent
            }
        } catch {
            // Revert on error
            if let index = contents.firstIndex(where: { $0.id == contentId }) {
                contents[index].isFavorited.toggle()
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
            var updatedContent = currentContent
            updatedContent.isUnliked.toggle()
            if updatedContent.isUnliked {
                // When unliked, mark as read in UI immediately
                if !updatedContent.isRead {
                    updatedContent = ContentSummary(
                        id: updatedContent.id,
                        contentType: updatedContent.contentType,
                        url: updatedContent.url,
                        title: updatedContent.title,
                        source: updatedContent.source,
                        platform: updatedContent.platform,
                        status: updatedContent.status,
                        shortSummary: updatedContent.shortSummary,
                        createdAt: updatedContent.createdAt,
                        processedAt: updatedContent.processedAt,
                        classification: updatedContent.classification,
                        publicationDate: updatedContent.publicationDate,
                        isRead: true,
                        isFavorited: updatedContent.isFavorited,
                        isUnliked: true
                    )

                    // Update unread counts
                    if updatedContent.contentType == "article" {
                        unreadCountService.decrementArticleCount()
                    } else if updatedContent.contentType == "podcast" {
                        unreadCountService.decrementPodcastCount()
                    }
                }
            }

            contents[index] = updatedContent

            // Make API call
            let response = try await contentService.toggleUnlike(id: contentId)

            // Update with server response
            let isUnliked = (response["is_unliked"] as? Bool) ?? updatedContent.isUnliked
            let isRead = (response["is_read"] as? Bool) ?? updatedContent.isRead

            var finalContent = updatedContent
            finalContent.isUnliked = isUnliked
            // Respect server read flag
            if isRead { finalContent = ContentSummary(
                id: finalContent.id,
                contentType: finalContent.contentType,
                url: finalContent.url,
                title: finalContent.title,
                source: finalContent.source,
                platform: finalContent.platform,
                status: finalContent.status,
                shortSummary: finalContent.shortSummary,
                createdAt: finalContent.createdAt,
                processedAt: finalContent.processedAt,
                classification: finalContent.classification,
                publicationDate: finalContent.publicationDate,
                isRead: true,
                isFavorited: finalContent.isFavorited,
                isUnliked: finalContent.isUnliked
            ) }

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
                contents[idx].isUnliked.toggle()
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
}
