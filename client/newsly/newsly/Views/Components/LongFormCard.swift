//
//  LongFormCard.swift
//  newsly
//
//  Hero image card for long-form content (articles/podcasts).
//

import SwiftUI

struct LongFormCard: View {
    let content: ContentSummary
    var onMarkRead: (() -> Void)?
    var onToggleFavorite: (() -> Void)?
    private let topicAccent = Color(red: 0.067, green: 0.322, blue: 0.831) // #1152d4

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Color.clear
                .frame(height: CardMetrics.heroImageHeight)
                .overlay {
                    GeometryReader { geo in
                        heroImage
                            .frame(width: geo.size.width, height: geo.size.height)
                    }
                }
                .clipped()
                .overlay(alignment: .bottom) {
                    LinearGradient(
                        stops: [
                            .init(color: .clear, location: 0.0),
                            .init(color: Color.surfacePrimary.opacity(0.35), location: 0.62),
                            .init(color: Color.surfacePrimary, location: 1.0),
                        ],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                }

            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 8) {
                    badgeView

                    if let relativeTime = content.relativeTimeDisplay {
                        Text(relativeTime)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(Color.textTertiary)
                    }
                }
                .padding(.bottom, 12)

                Text(content.displayTitle)
                    .font(.cardHeadline)
                    .foregroundColor(content.isRead ? .secondary : Color.textPrimary)
                    .lineLimit(3)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.bottom, 8)

                if let summary = summaryText {
                    Text(summary)
                        .font(.cardDescription)
                        .foregroundStyle(Color.textSecondary)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)
                        .padding(.bottom, 16)
                }

                Divider()
                    .foregroundStyle(Color.borderSubtle.opacity(0.5))
                    .padding(.top, 4)

                HStack {
                    Text(sourceLabel)
                        .font(.cardFooter)
                        .tracking(0.5)
                        .foregroundStyle(Color.textTertiary)
                        .lineLimit(1)

                    Spacer()

                    HStack(spacing: 12) {
                        Button {
                            onMarkRead?()
                        } label: {
                            Image(systemName: content.isRead ? "checkmark.circle.fill" : "checkmark.circle")
                                .font(.system(size: 20))
                                .foregroundStyle(content.isRead ? Color.textTertiary.opacity(0.5) : Color.textTertiary)
                        }
                        .buttonStyle(.plain)

                        Button {
                            onToggleFavorite?()
                        } label: {
                            Image(systemName: content.isFavorited ? "star.fill" : "star")
                                .font(.system(size: 20))
                                .foregroundStyle(content.isFavorited ? topicAccent : Color.textTertiary)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.top, 8)
            }
            .padding(.horizontal, 24)
            .padding(.top, 24)
            .padding(.bottom, 24)
            .offset(y: CardMetrics.textOverlapOffset)
            .padding(.bottom, CardMetrics.textOverlapOffset)
            .background(
                LinearGradient(
                    stops: [
                        .init(color: .clear, location: 0),
                        .init(color: Color.surfacePrimary, location: 0.25),
                        .init(color: Color.surfacePrimary, location: 1.0),
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .offset(y: CardMetrics.textOverlapOffset)
                .padding(.bottom, CardMetrics.textOverlapOffset)
            )
        }
        .background(Color.surfacePrimary)
        .clipShape(RoundedRectangle(cornerRadius: CardMetrics.cardCornerRadius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: CardMetrics.cardCornerRadius, style: .continuous)
                .stroke(Color.borderSubtle.opacity(0.5), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.08), radius: 10, x: 0, y: 3)
    }

    @ViewBuilder
    private var badgeView: some View {
        Text(badgeLabel)
            .font(.cardBadge)
            .tracking(0.5)
            .foregroundStyle(topicAccent)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(topicAccent.opacity(0.1))
            .clipShape(Capsule())
    }

    @ViewBuilder
    private var heroImage: some View {
        let displayUrl = content.imageUrl ?? content.thumbnailUrl
        if let urlString = displayUrl, let url = buildImageURL(from: urlString) {
            CachedAsyncImage(url: url) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } placeholder: {
                placeholderGradient
            }
        } else {
            placeholderGradient
        }
    }

    private var placeholderGradient: some View {
        LinearGradient(
            colors: [Color.surfaceSecondary, Color.surfaceTertiary],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .overlay(
            Image(systemName: contentTypeIcon)
                .font(.system(size: 40))
                .foregroundStyle(Color.textTertiary.opacity(0.4))
        )
    }

    private var summaryText: String? {
        if let shortSummary = content.shortSummary, !shortSummary.isEmpty {
            return shortSummary
        }
        if let newsSummary = content.newsSummary, !newsSummary.isEmpty {
            return newsSummary
        }
        return nil
    }

    private var sourceLabel: String {
        if let source = content.source, !source.isEmpty {
            return source.uppercased()
        }
        if let platform = content.platform, !platform.isEmpty {
            return platform.uppercased()
        }
        if let typeName = content.contentTypeEnum?.displayName {
            return typeName.uppercased()
        }
        return "NEWSLY"
    }

    private var badgeLabel: String {
        if let primaryTopic = content.primaryTopic, !primaryTopic.isEmpty {
            return primaryTopic.uppercased()
        }
        if let typeName = content.contentTypeEnum?.displayName {
            return typeName.uppercased()
        }
        return "ARTICLE"
    }

    private var contentTypeIcon: String {
        switch content.contentTypeEnum {
        case .article:
            return "doc.text"
        case .podcast:
            return "headphones"
        default:
            return "doc"
        }
    }

    private func buildImageURL(from urlString: String) -> URL? {
        if urlString.hasPrefix("http://") || urlString.hasPrefix("https://") {
            return URL(string: urlString)
        }
        let baseURL = AppSettings.shared.baseURL
        let fullURL = urlString.hasPrefix("/") ? baseURL + urlString : baseURL + "/" + urlString
        return URL(string: fullURL)
    }
}
