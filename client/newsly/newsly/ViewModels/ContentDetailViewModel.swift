//
//  ContentDetailViewModel.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation
import SwiftUI
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "ContentDetail")

enum ShareContentOption {
    case light
    case medium
    case full
}

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
        logger.info("[ContentDetail] loadContent started | contentId=\(self.contentId)")
        isLoading = true
        errorMessage = nil

        do {
            logger.debug("[ContentDetail] Fetching content detail | contentId=\(self.contentId)")
            let fetched = try await contentService.fetchContentDetail(id: contentId)
            content = fetched
            logger.info("[ContentDetail] Content fetched | contentId=\(self.contentId) type=\(fetched.contentType, privacy: .public) isRead=\(fetched.isRead) title=\(fetched.displayTitle, privacy: .public)")

            // Capture read state as returned by the server BEFORE any auto-marking
            wasAlreadyReadWhenLoaded = fetched.isRead
            logger.debug("[ContentDetail] wasAlreadyReadWhenLoaded=\(fetched.isRead) | contentId=\(self.contentId)")

            // Auto-mark as read if not already read
            if !fetched.isRead {
                logger.info("[ContentDetail] Content not read, marking as read | contentId=\(self.contentId) type=\(fetched.contentType, privacy: .public)")
                try await contentService.markContentAsRead(id: contentId)
                logger.info("[ContentDetail] Successfully marked as read | contentId=\(self.contentId)")

                // Post notification so list views can update their local state
                logger.debug("[ContentDetail] Posting contentMarkedAsRead notification | contentId=\(self.contentId) type=\(fetched.contentType, privacy: .public)")
                NotificationCenter.default.post(
                    name: .contentMarkedAsRead,
                    object: nil,
                    userInfo: ["contentId": contentId, "contentType": fetched.contentType]
                )

                // Update unread count based on content type
                if fetched.contentType == "article" {
                    logger.debug("[ContentDetail] Decrementing article count | contentId=\(self.contentId)")
                    unreadCountService.decrementArticleCount()
                } else if fetched.contentType == "podcast" {
                    logger.debug("[ContentDetail] Decrementing podcast count | contentId=\(self.contentId)")
                    unreadCountService.decrementPodcastCount()
                } else if fetched.contentType == "news" {
                    logger.debug("[ContentDetail] Decrementing news count | contentId=\(self.contentId)")
                    unreadCountService.decrementNewsCount()
                }
            } else {
                logger.info("[ContentDetail] Content already read, skipping mark-as-read | contentId=\(self.contentId)")
            }
        } catch {
            logger.error("[ContentDetail] Error loading content | contentId=\(self.contentId) error=\(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }

        isLoading = false
        logger.debug("[ContentDetail] loadContent completed | contentId=\(self.contentId)")
    }
    
    func shareContent(option: ShareContentOption) {
        let items = buildShareItems(option: option)
        guard !items.isEmpty else { return }

        let activityVC = UIActivityViewController(activityItems: items, applicationActivities: nil)

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

    private func buildMediumMarkdown() -> String? {
        guard let content = content else { return nil }

        var sections: [String] = []
        sections.append("# \(content.displayTitle)")

        var keyPoints = content.structuredSummary?.bulletPoints ?? content.bulletPoints

        // For news content, extract key points from newsMetadata
        if keyPoints.isEmpty, content.contentType == "news",
           let newsKeyPoints = content.newsMetadata?.summary?.keyPoints, !newsKeyPoints.isEmpty {
            keyPoints = newsKeyPoints.map { BulletPoint(text: $0, category: nil) }
        }

        if keyPoints.isEmpty, let summary = content.summary, !summary.isEmpty {
            keyPoints = [BulletPoint(text: summary, category: nil)]
        } else if keyPoints.isEmpty, let shortSummary = content.shortSummary, !shortSummary.isEmpty {
            keyPoints = [BulletPoint(text: shortSummary, category: nil)]
        }

        if !keyPoints.isEmpty {
            let bullets = keyPoints.map { "- \($0.text)" }.joined(separator: "\n")
            sections.append("## Key Points\n\(bullets)")
        }

        let quotes = content.structuredSummary?.quotes ?? content.quotes
        if !quotes.isEmpty {
            let quoteText = quotes.map { "> \($0.text)" }.joined(separator: "\n")
            sections.append("## Quotes\n\(quoteText)")
        }

        if !content.url.isEmpty {
            sections.append("Link: \(content.url)")
        }

        guard sections.count > 1 else { return nil }
        return sections.joined(separator: "\n\n")
    }

    private func buildShareItems(option: ShareContentOption) -> [Any] {
        guard let content = content else { return [] }

        switch option {
        case .light:
            guard let url = URL(string: content.url) else { return [] }
            return [content.displayTitle, url]
        case .medium:
            if let mediumText = buildMediumMarkdown() {
                return [MarkdownItemProvider(markdown: mediumText)]
            }
            return buildShareItems(option: .light)
        case .full:
            if let fullText = buildFullMarkdown() {
                return [MarkdownItemProvider(markdown: fullText)]
            }
            return buildShareItems(option: .medium)
        }
    }

    func openInChatGPT() async {
        // Strategy:
        // 1) Build full markdown and offer it via the share sheet so ChatGPT's share extension can receive the text.
        // 2) As a convenience, also put the text on the clipboard (user can paste if needed in the app).
        // 3) Use custom item provider to preserve line breaks in Mail by converting to HTML.

        guard let content = content else { return }
        let fullText = buildFullMarkdown() ?? content.displayTitle

        // Put on clipboard (helps in case target app reads clipboard or the user wants to paste manually)
        UIPasteboard.general.string = fullText

        // Create custom item provider that converts markdown to HTML for Mail
        let itemProvider = MarkdownItemProvider(markdown: fullText)

        // Prepare share sheet with custom provider
        let activityVC = UIActivityViewController(activityItems: [itemProvider], applicationActivities: nil)
        activityVC.excludedActivityTypes = [.assignToContact, .saveToCameraRoll, .addToReadingList, .postToFacebook, .postToTwitter]

        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let root = windowScene.windows.first?.rootViewController {
            root.present(activityVC, animated: true)
        }
    }
}

// MARK: - Custom Item Provider for Markdown Sharing
class MarkdownItemProvider: NSObject, UIActivityItemSource {
    private let markdown: String

    init(markdown: String) {
        self.markdown = markdown
        super.init()
    }

    func activityViewControllerPlaceholderItem(_ activityViewController: UIActivityViewController) -> Any {
        return markdown
    }

    func activityViewController(_ activityViewController: UIActivityViewController, itemForActivityType activityType: UIActivity.ActivityType?) -> Any? {
        // For Mail, convert markdown to HTML to preserve line breaks
        if activityType == .mail {
            return convertMarkdownToHTML(markdown)
        }
        // For other activities, return plain markdown text
        return markdown
    }

    private func convertMarkdownToHTML(_ markdown: String) -> String {
        var html = "<html><body style='font-family: -apple-system, sans-serif; font-size: 14px; line-height: 1.6;'>"

        // Split into paragraphs and convert
        let paragraphs = markdown.components(separatedBy: "\n\n")

        for paragraph in paragraphs {
            var processedParagraph = paragraph

            // Convert headers
            if processedParagraph.hasPrefix("### ") {
                processedParagraph = "<h3>" + processedParagraph.dropFirst(4) + "</h3>"
            } else if processedParagraph.hasPrefix("## ") {
                processedParagraph = "<h2>" + processedParagraph.dropFirst(3) + "</h2>"
            } else if processedParagraph.hasPrefix("# ") {
                processedParagraph = "<h1>" + processedParagraph.dropFirst(2) + "</h1>"
            } else if processedParagraph.hasPrefix("---") {
                processedParagraph = "<hr/>"
            } else if processedParagraph.contains("\n- ") || processedParagraph.hasPrefix("- ") {
                // Convert bullet lists
                let items = processedParagraph.components(separatedBy: "\n").filter { $0.hasPrefix("- ") }
                let listItems = items.map { "<li>" + $0.dropFirst(2) + "</li>" }.joined()
                processedParagraph = "<ul>" + listItems + "</ul>"
            } else if processedParagraph.contains("\n> ") || processedParagraph.hasPrefix("> ") {
                // Convert quotes
                let quotes = processedParagraph.components(separatedBy: "\n").filter { $0.hasPrefix("> ") }
                let quoteText = quotes.map { String($0.dropFirst(2)) }.joined(separator: "<br/>")
                processedParagraph = "<blockquote style='border-left: 3px solid #ccc; padding-left: 10px; margin: 10px 0;'>" + quoteText + "</blockquote>"
            } else if !processedParagraph.isEmpty {
                // Regular paragraph - convert single newlines to <br/>
                processedParagraph = "<p>" + processedParagraph.replacingOccurrences(of: "\n", with: "<br/>") + "</p>"
            }

            html += processedParagraph
        }

        html += "</body></html>"
        return html
    }
}
