//
//  ArticleCardView.swift
//  newsly
//
//  Individual card component for the article/podcast card stack.
//

import SwiftUI

struct ArticleCardView: View {
    let content: ContentSummary
    let keyPoints: [String]?
    let hook: String?
    let topics: [String]?
    let isLoadingKeyPoints: Bool
    let onFavorite: () -> Void
    let onMarkRead: () -> Void
    let onTap: () -> Void

    var scale: CGFloat = 1.0
    var yOffset: CGFloat = 0
    var cardOpacity: Double = 1.0

    private let cardCornerRadius: CGFloat = 20
    private let heroImageHeight: CGFloat = 200

    var body: some View {
        Button(action: onTap) {
            cardContent
        }
        .buttonStyle(.plain)
        .scaleEffect(scale)
        .offset(y: yOffset)
        .opacity(cardOpacity)
    }

    private var cardContent: some View {
        VStack(alignment: .leading, spacing: 0) {
            heroImageSection

            VStack(alignment: .leading, spacing: 12) {
                titleSection
                metadataRow
                hookSection
                keyPointsSection
                Spacer(minLength: 8)
                actionButtonsRow
            }
            .padding(20)
        }
        .background(Color(.systemGray6))
        .cornerRadius(cardCornerRadius)
        .shadow(color: .black.opacity(0.25), radius: 12, x: 0, y: 6)
    }

    @ViewBuilder
    private var heroImageSection: some View {
        ZStack(alignment: .topTrailing) {
            if let imageUrlString = content.imageUrl,
               let imageUrl = buildImageURL(from: imageUrlString) {
                // Use progressive loading: thumbnail first, then full image
                let thumbnailUrl = content.thumbnailUrl.flatMap { buildImageURL(from: $0) }
                let _ = print("ArticleCardView: imageUrl=\(imageUrl), thumbnailUrl=\(thumbnailUrl?.absoluteString ?? "nil")")
                CachedAsyncImage(
                    url: imageUrl,
                    thumbnailUrl: thumbnailUrl
                ) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(height: heroImageHeight)
                        .clipped()
                } placeholder: {
                    placeholderImage
                }
            } else {
                let _ = print("ArticleCardView: No image URL for content \(content.id), imageUrl=\(content.imageUrl ?? "nil")")
                placeholderImage
            }

            contentTypeBadge
                .padding(12)
        }
        .frame(height: heroImageHeight)
        .clipShape(
            UnevenRoundedRectangle(
                topLeadingRadius: cardCornerRadius,
                bottomLeadingRadius: 0,
                bottomTrailingRadius: 0,
                topTrailingRadius: cardCornerRadius
            )
        )
    }

    private var placeholderImage: some View {
        Rectangle()
            .fill(
                LinearGradient(
                    colors: [Color(.systemGray4), Color(.systemGray5)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .frame(height: heroImageHeight)
            .overlay(
                Image(systemName: contentTypeIcon)
                    .font(.system(size: 48, weight: .light))
                    .foregroundColor(.white.opacity(0.5))
            )
    }

    private var contentTypeBadge: some View {
        HStack(spacing: 4) {
            Image(systemName: contentTypeIcon)
                .font(.caption)
            Text(content.contentType.capitalized)
                .font(.caption)
                .fontWeight(.medium)
        }
        .foregroundColor(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(.ultraThinMaterial)
        .cornerRadius(12)
    }

    private var titleSection: some View {
        Text(content.displayTitle)
            .font(.title2)
            .fontWeight(.bold)
            .foregroundColor(.primary)
            .lineLimit(3)
            .multilineTextAlignment(.leading)
    }

    private var metadataRow: some View {
        HStack(spacing: 8) {
            if let source = content.source {
                Text(source)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }

            if content.source != nil {
                Circle()
                    .fill(Color.secondary.opacity(0.5))
                    .frame(width: 4, height: 4)
            }

            Text(content.formattedDate)
                .font(.subheadline)
                .foregroundColor(.secondary)

            Spacer()

            if content.isRead {
                Image(systemName: "checkmark.circle.fill")
                    .font(.caption)
                    .foregroundColor(.green)
            }
        }
    }

    @ViewBuilder
    private var hookSection: some View {
        if let hookText = hook, !hookText.isEmpty {
            Text(hookText)
                .font(.subheadline)
                .fontWeight(.medium)
                .italic()
                .foregroundColor(.primary.opacity(0.85))
                .padding(.vertical, 4)
        }
    }

    @ViewBuilder
    private var topicsSection: some View {
        if let topicsList = topics, !topicsList.isEmpty {
            FlowLayout(spacing: 6) {
                ForEach(topicsList.prefix(5), id: \.self) { topic in
                    Text(topic)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.accentColor)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(Color.accentColor.opacity(0.12))
                        .cornerRadius(12)
                }
            }
        }
    }

    @ViewBuilder
    private var keyPointsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Key Points")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)
                .textCase(.uppercase)
                .tracking(0.5)

            if isLoadingKeyPoints {
                skeletonKeyPoints
            } else if let points = keyPoints, !points.isEmpty {
                ForEach(points.prefix(4), id: \.self) { point in
                    keyPointRow(point)
                }
            } else if let summary = content.shortSummary, !summary.isEmpty {
                Text(summary)
                    .font(.subheadline)
                    .foregroundColor(.primary.opacity(0.85))
                    .lineLimit(4)
            } else {
                Text("No summary available")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .italic()
            }
        }
    }

    private func keyPointRow(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(Color.accentColor)
                .frame(width: 6, height: 6)
                .padding(.top, 6)

            Text(text)
                .font(.subheadline)
                .foregroundColor(.primary.opacity(0.9))
                .multilineTextAlignment(.leading)
        }
    }

    private var skeletonKeyPoints: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(0..<3, id: \.self) { index in
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color(.systemGray4))
                    .frame(height: 14)
                    .frame(maxWidth: skeletonWidth(for: index))
            }
        }
    }

    private func skeletonWidth(for index: Int) -> CGFloat {
        switch index {
        case 0: return .infinity
        case 1: return 280
        default: return 200
        }
    }

    private var actionButtonsRow: some View {
        HStack(spacing: 20) {
            Button(action: onMarkRead) {
                HStack(spacing: 6) {
                    Image(systemName: content.isRead ? "checkmark.circle.fill" : "circle")
                        .font(.body)
                    Text(content.isRead ? "Read" : "Mark as Read")
                        .font(.subheadline)
                        .fontWeight(.medium)
                }
                .foregroundColor(content.isRead ? .green : .primary)
            }

            Spacer()

            Button(action: onFavorite) {
                Image(systemName: content.isFavorited ? "star.fill" : "star")
                    .font(.title3)
                    .foregroundColor(content.isFavorited ? .yellow : .primary.opacity(0.7))
            }
        }
        .padding(.top, 4)
    }

    private var contentTypeIcon: String {
        switch content.contentType {
        case "article":
            return "doc.text"
        case "podcast":
            return "headphones"
        default:
            return "newspaper"
        }
    }

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
