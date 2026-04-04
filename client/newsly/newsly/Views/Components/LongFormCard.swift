//
//  LongFormCard.swift
//  newsly
//
//  Hero image card for long-form content (articles/podcasts).
//

import SwiftUI

struct LongFormCard: View {
    let content: ContentSummary
    var variant: Variant = .hero
    var onMarkRead: (() -> Void)?
    var onToggleFavorite: (() -> Void)?

    enum Variant {
        case hero
        case compact
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Image section with gradient overlay
            Color.clear
                .frame(height: variant == .hero ? 220 : 160)
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
                            .init(color: Color.surfaceSecondary.opacity(0.35), location: 0.62),
                            .init(color: Color.surfaceSecondary, location: 1.0),
                        ],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                }

            VStack(alignment: .leading, spacing: 0) {
                // Badge + metadata
                HStack(spacing: 8) {
                    badgeView

                    if let relativeTime = content.relativeTimeDisplay {
                        Text(relativeTime)
                            .font(.terracottaBodySmall)
                            .foregroundStyle(Color.onSurfaceSecondary)
                    }
                }
                .padding(.bottom, 8)

                // Headline
                Text(content.displayTitle)
                    .font(variant == .hero ? .terracottaHeadlineLarge : .terracottaHeadlineSmall)
                    .foregroundColor(content.isRead ? Color.onSurfaceSecondary : Color.onSurface)
                    .lineLimit(variant == .hero ? 3 : 2)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.bottom, 8)

                // Description (hero only gets more lines)
                if let summary = summaryText {
                    Text(summary)
                        .font(variant == .hero ? .terracottaBodyMedium : .terracottaBodySmall)
                        .foregroundStyle(Color.onSurfaceSecondary)
                        .lineLimit(variant == .hero ? 3 : 2)
                        .multilineTextAlignment(.leading)
                        .padding(.bottom, 12)
                }

                // Footer: source + actions (hero variant only)
                if variant == .hero {
                    HStack {
                        Text(sourceLabel)
                            .font(.terracottaBodySmall)
                            .tracking(0.5)
                            .foregroundStyle(Color.onSurfaceSecondary)
                            .lineLimit(1)

                        Spacer()

                        HStack(spacing: 12) {
                            Button {
                                onMarkRead?()
                            } label: {
                                Image(systemName: content.isRead ? "checkmark.circle.fill" : "checkmark.circle")
                                    .font(.system(size: 20))
                                    .foregroundStyle(content.isRead ? Color.onSurfaceSecondary.opacity(0.5) : Color.onSurfaceSecondary)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("long.action.mark_read.\(content.id)")

                            Button {
                                onToggleFavorite?()
                            } label: {
                                Image(systemName: content.isFavorited ? "star.fill" : "star")
                                    .font(.system(size: 20))
                                    .foregroundStyle(content.isFavorited ? Color.terracottaPrimary : Color.onSurfaceSecondary)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("long.action.favorite.\(content.id)")
                        }
                    }
                    .padding(.top, 4)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 14)
            .offset(y: CardMetrics.textOverlapOffset)
            .padding(.bottom, CardMetrics.textOverlapOffset)
            .background(
                LinearGradient(
                    stops: [
                        .init(color: .clear, location: 0),
                        .init(color: Color.surfaceSecondary, location: 0.25),
                        .init(color: Color.surfaceSecondary, location: 1.0),
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .offset(y: CardMetrics.textOverlapOffset)
                .padding(.bottom, CardMetrics.textOverlapOffset)
            )
        }
        .background(Color.surfaceSecondary)
        .clipShape(RoundedRectangle(cornerRadius: CardMetrics.cardCornerRadius, style: .continuous))
        .shadow(color: Color.onSurface.opacity(0.06), radius: 32, x: 0, y: 8)
    }

    @ViewBuilder
    private var badgeView: some View {
        Text(badgeLabel)
            .font(.terracottaCategoryPill)
            .tracking(0.5)
            .foregroundStyle(Color.terracottaPrimary)
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(Color.terracottaPrimary.opacity(0.1))
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
            colors: [Color.surfaceContainer, Color.surfaceContainerHigh],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .overlay(
            Image(systemName: contentTypeIcon)
                .font(.system(size: 40))
                .foregroundStyle(Color.onSurfaceSecondary.opacity(0.3))
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
