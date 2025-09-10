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
            content = try await contentService.fetchContentDetail(id: contentId)
            
            // Auto-mark as read if not already read
            if let content = content, !content.isRead {
                try await contentService.markContentAsRead(id: contentId)
                
                // Update unread count based on content type
                if content.contentType == "article" {
                    unreadCountService.decrementArticleCount()
                } else if content.contentType == "podcast" {
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
    
    func copyPodcastContent() {
        guard let content = content else { return }
        
        var fullText = "# \(content.displayTitle)\n\n"
        
        // Add metadata
        if let source = content.source {
            fullText += "Source: \(source)\n"
        }
        if let pubDate = content.publicationDate {
            fullText += "Published: \(pubDate)\n"
        }
        if !content.url.isEmpty {
            fullText += "URL: \(content.url)\n"
        }
        fullText += "\n---\n\n"
        
        // Add structured summary if available
        if let structuredSummary = content.structuredSummary {
            fullText += "## Summary\n\n"
            
            if !structuredSummary.topics.isEmpty {
                fullText += "### Key Topics\n"
                for topic in structuredSummary.topics {
                    fullText += "- \(topic)\n"
                }
                fullText += "\n"
            }
            
            if !structuredSummary.bulletPoints.isEmpty {
                fullText += "### Main Points\n"
                for point in structuredSummary.bulletPoints {
                    fullText += "- \(point.text)\n"
                }
                fullText += "\n"
            }
            
            if !structuredSummary.quotes.isEmpty {
                fullText += "### Notable Quotes\n"
                for quote in structuredSummary.quotes {
                    fullText += "> \(quote.text)\n\n"
                }
            }
            
            // Add overview if available
            if let overview = structuredSummary.overview {
                fullText += "### Overview\n"
                fullText += "\(overview)\n\n"
            }
            
            fullText += "---\n\n"
        }
        
        // Add full transcript
        // For podcasts, check podcastMetadata.transcript first, then fall back to fullMarkdown
        if content.contentType == "podcast", let podcastMetadata = content.podcastMetadata, let transcript = podcastMetadata.transcript {
            fullText += "## Full Transcript\n\n"
            fullText += transcript
        } else if let fullMarkdown = content.fullMarkdown {
            fullText += "## Full Transcript\n\n"
            fullText += fullMarkdown
        }
        
        // Copy to clipboard
        UIPasteboard.general.string = fullText
        
        // Optionally, you could show a confirmation using a toast or alert
        // For now, the copy happens silently
    }
    
    func openInChatGPT() async {
        guard let content = content else { return }
        do {
            let chatURLString = try await contentService.getChatGPTUrl(id: content.id)
            guard let webURL = URL(string: chatURLString) else {
                errorMessage = "Invalid ChatGPT URL returned by API"
                return
            }
            ChatGPTDeepLink.openPreferApp(fallbackWebURL: webURL) { success in
                if !success {
                    // Finally fall back to web URL
                    ChatGPTDeepLink.openWeb(webURL)
                }
            }
        } catch {
            errorMessage = "Failed to open ChatGPT: \(error.localizedDescription)"
        }
    }
}
