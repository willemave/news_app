//
//  ContentDetailViewModel.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation
import SwiftUI

@MainActor
class ContentDetailViewModel: ObservableObject {
    @Published var content: ContentDetail?
    @Published var isLoading = false
    @Published var errorMessage: String?
    // Indicates if the item was already marked as read when it was fetched
    @Published var wasAlreadyReadWhenLoaded: Bool = false
    
    private let contentService = ContentService.shared
    private let unreadCountService = UnreadCountService.shared
    private var contentId: Int = 0
    
    init(contentId: Int = 0) {
        self.contentId = contentId
    }
    
    func updateContentId(_ newId: Int) {
        self.contentId = newId
        // Clear previous content to show loading state
        self.content = nil
    }
    
    func loadContent() async {
        isLoading = true
        errorMessage = nil
        
        do {
            let fetched = try await contentService.fetchContentDetail(id: contentId)
            content = fetched
            
            // Capture read state as returned by the server BEFORE any auto-marking
            wasAlreadyReadWhenLoaded = fetched.isRead
            
            // Auto-mark as read if not already read
            if !fetched.isRead {
                try await contentService.markContentAsRead(id: contentId)
                
                // Update unread count based on content type
                if fetched.contentType == "article" {
                    unreadCountService.decrementArticleCount()
                } else if fetched.contentType == "podcast" {
                    unreadCountService.decrementPodcastCount()
                }
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func shareContent() {
        guard let content = content, let url = URL(string: content.url) else { return }
        
        let activityVC = UIActivityViewController(
            activityItems: [url, content.displayTitle],
            applicationActivities: nil
        )
        
        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let rootViewController = windowScene.windows.first?.rootViewController {
            rootViewController.present(activityVC, animated: true)
        }
    }
    
    func toggleFavorite() async {
        guard let currentContent = content else { return }
        
        do {
            // Optimistically update the UI
            content?.isFavorited.toggle()
            
            // Make API call
            let response = try await contentService.toggleFavorite(id: currentContent.id)
            
            // Update with server response
            if let isFavorited = response["is_favorited"] as? Bool {
                content?.isFavorited = isFavorited
            }
        } catch {
            // Revert on error
            content?.isFavorited = currentContent.isFavorited
            errorMessage = "Failed to update favorite status"
        }
    }
    
    func toggleUnlike() async {
        guard let currentContent = content else { return }
        do {
            // Optimistic UI update
            content?.isUnliked.toggle()
            if content?.isUnliked == true {
                // Mark as read locally
                if content?.isRead == false {
                    content?.isRead = true
                    // Update unread count based on content type
                    if currentContent.contentType == "article" {
                        unreadCountService.decrementArticleCount()
                    } else if currentContent.contentType == "podcast" {
                        unreadCountService.decrementPodcastCount()
                    }
                }
            }

            // API call
            let response = try await contentService.toggleUnlike(id: currentContent.id)
            if let isUnliked = response["is_unliked"] as? Bool {
                content?.isUnliked = isUnliked
            }
            if let isRead = response["is_read"] as? Bool, isRead {
                content?.isRead = true
            }
        } catch {
            // Revert on error
            content?.isUnliked = currentContent.isUnliked
            errorMessage = "Failed to update unlike status"
        }
    }
    
    private func buildFullMarkdown() -> String? {
        guard let content = content else { return nil }

        var fullText = "# \(content.displayTitle)\n\n"

        // Add metadata
        if let source = content.source { fullText += "Source: \(source)\n" }
        if let pubDate = content.publicationDate { fullText += "Published: \(pubDate)\n" }
        if !content.url.isEmpty { fullText += "URL: \(content.url)\n" }
        fullText += "\n---\n\n"

        // Structured summary
        if let structuredSummary = content.structuredSummary {
            fullText += "## Summary\n\n"
            if !structuredSummary.topics.isEmpty {
                fullText += "### Key Topics\n" + structuredSummary.topics.map { "- \($0)" }.joined(separator: "\n") + "\n\n"
            }
            if !structuredSummary.bulletPoints.isEmpty {
                fullText += "### Main Points\n" + structuredSummary.bulletPoints.map { "- \($0.text)" }.joined(separator: "\n") + "\n\n"
            }
            if !structuredSummary.quotes.isEmpty {
                fullText += "### Notable Quotes\n" + structuredSummary.quotes.map { "> \($0.text)\n" }.joined() + "\n"
            }
            if let overview = structuredSummary.overview {
                fullText += "### Overview\n\(overview)\n\n"
            }
            fullText += "---\n\n"
        }

        // Full content / transcript
        if content.contentType == "podcast", let podcastMetadata = content.podcastMetadata, let transcript = podcastMetadata.transcript {
            fullText += "## Full Transcript\n\n" + transcript
        } else if let fullMarkdown = content.fullMarkdown {
            fullText += (content.contentType == "podcast" ? "## Transcript\n\n" : "## Full Article\n\n")
            fullText += fullMarkdown
        }
        return fullText
    }

    func copyPodcastContent() {
        guard let fullText = buildFullMarkdown() else { return }
        UIPasteboard.general.string = fullText
    }
    
    func openInChatGPT() async {
        // Strategy:
        // 1) Build full markdown and offer it via the share sheet so ChatGPT's share extension can receive the text.
        // 2) As a convenience, also put the text on the clipboard (user can paste if needed in the app).
        // 3) Try to open the ChatGPT app using universal link (web URL) so that, if supported, it lands in-app.

        guard let content = content else { return }
        let fullText = buildFullMarkdown() ?? content.displayTitle

        // Put on clipboard (helps in case target app reads clipboard or the user wants to paste manually)
        UIPasteboard.general.string = fullText

        // Prepare share sheet with the full markdown text
        let activityVC = UIActivityViewController(activityItems: [fullText], applicationActivities: nil)
        activityVC.excludedActivityTypes = [.assignToContact, .saveToCameraRoll, .addToReadingList, .postToFacebook, .postToTwitter]

        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let root = windowScene.windows.first?.rootViewController {
            root.present(activityVC, animated: true)
        }
    }
}
