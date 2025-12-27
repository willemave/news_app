//
//  ContentCard.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI

struct ContentCard: View {
    let content: ContentSummary
    let dimReadState: Bool

    init(
        content: ContentSummary,
        dimReadState: Bool = true
    ) {
        self.content = content
        self.dimReadState = dimReadState
    }

    private let thumbnailSize: CGFloat = 60

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            // Thumbnail on left
            thumbnailView

            // Main content
            VStack(alignment: .leading, spacing: 6) {
                // Title
                Text(content.displayTitle)
                    .font(.body)
                    .fontWeight(.semibold)
                    .foregroundColor(dimReadState && content.isRead ? .secondary : .primary)
                    .lineLimit(3)
                    .truncationMode(.tail)

                // Platform icon + Source + Date
                HStack(spacing: 6) {
                    PlatformIcon(platform: content.platform)
                        .opacity(content.platform == nil ? 0 : 1)
                    if let source = content.source {
                        Text(source)
                            .font(.footnote)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                    if let processedDate = content.processedDateDisplay {
                        Text(processedDate)
                            .font(.footnote)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .frame(minHeight: 76, alignment: .center)
        .opacity(dimReadState && content.isRead ? 0.85 : 1.0)
    }

    @ViewBuilder
    private var thumbnailView: some View {
        // Prefer thumbnail URL for faster loading, fall back to full image
        let displayUrl = content.thumbnailUrl ?? content.imageUrl
        if let imageUrlString = displayUrl,
           let imageUrl = buildImageURL(from: imageUrlString) {
            CachedAsyncImage(url: imageUrl) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: thumbnailSize, height: thumbnailSize)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } placeholder: {
                ProgressView()
                    .frame(width: thumbnailSize, height: thumbnailSize)
            }
        } else {
            thumbnailPlaceholder
        }
    }

    private var thumbnailPlaceholder: some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(Color.secondary.opacity(0.15))
            .frame(width: thumbnailSize, height: thumbnailSize)
            .overlay(
                Image(systemName: contentTypeIcon)
                    .font(.system(size: 20))
                    .foregroundColor(.secondary.opacity(0.6))
            )
    }

    private var contentTypeIcon: String {
        switch content.contentTypeEnum {
        case .article:
            return "doc.text"
        case .podcast:
            return "headphones"
        case .news:
            return "newspaper"
        default:
            return "doc"
        }
    }

    /// Build a full URL for the image, handling relative paths
    private func buildImageURL(from urlString: String) -> URL? {
        // If it's already a full URL, use it
        if urlString.hasPrefix("http://") || urlString.hasPrefix("https://") {
            return URL(string: urlString)
        }

        // Otherwise, it's a relative path - prepend base URL
        // Use string concatenation instead of appendingPathComponent to preserve path structure
        let baseURL = AppSettings.shared.baseURL
        let fullURL = urlString.hasPrefix("/") ? baseURL + urlString : baseURL + "/" + urlString
        return URL(string: fullURL)
    }
}
