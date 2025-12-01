//
//  ContentCard.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI

struct ContentCard: View {
    let content: ContentSummary
    let onMarkAsRead: () async -> Void
    let onToggleFavorite: () async -> Void
    let dimReadState: Bool

    init(
        content: ContentSummary,
        onMarkAsRead: @escaping () async -> Void,
        onToggleFavorite: @escaping () async -> Void,
        dimReadState: Bool = true
    ) {
        self.content = content
        self.onMarkAsRead = onMarkAsRead
        self.onToggleFavorite = onToggleFavorite
        self.dimReadState = dimReadState
    }

    @State private var isMarking = false
    @State private var isTogglingFavorite = false

    // Larger touch targets for better ergonomics (slightly narrower)
    private let actionSize: CGFloat = 36

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            // Main content
            VStack(alignment: .leading, spacing: 6) {
                // Title
                Text(content.displayTitle)
                    .font(.body)
                    .fontWeight(.semibold)
                    .foregroundColor(dimReadState && content.isRead ? .secondary : .primary)
                    .lineLimit(5)
                    .truncationMode(.tail)

                // Platform • Source • Processed date
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
                    if content.isAggregate {
                        Text("Aggregate")
                            .font(.caption2)
                            .fontWeight(.medium)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.blue.opacity(0.1))
                            .foregroundColor(.blue)
                            .clipShape(Capsule())
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            // Trailing action buttons (stacked vertically)
            VStack(spacing: 8) {
                // Favorite toggle
                Button(action: {
                    guard !isTogglingFavorite else { return }
                    isTogglingFavorite = true
                    Task {
                        await onToggleFavorite()
                        isTogglingFavorite = false
                    }
                }) {
                    Image(systemName: content.isFavorited ? "star.fill" : "star")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(content.isFavorited ? .yellow : .secondary)
                        .frame(width: actionSize, height: actionSize)
                        .background(
                            Circle()
                                .fill(Color.secondary.opacity(0.12))
                        )
                }
                .buttonStyle(.borderless)
                .accessibilityLabel(content.isFavorited ? "Unfavorite" : "Favorite")

                // Mark as read
                Button(action: {
                    guard !content.isRead, !isMarking else { return }
                    isMarking = true
                    Task {
                        await onMarkAsRead()
                        isMarking = false
                    }
                }) {
                    Image(systemName: content.isRead ? "checkmark.circle.fill" : "checkmark.circle")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(content.isRead ? .green : .secondary)
                        .frame(width: actionSize, height: actionSize)
                        .background(
                            Circle()
                                .fill(Color.secondary.opacity(0.12))
                        )
                }
                .buttonStyle(.borderless)
                .disabled(content.isRead)
                .opacity(content.isRead ? 0.5 : 1)
                .accessibilityLabel("Mark as Read")
            }
            .frame(width: actionSize)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .frame(minHeight: 84, alignment: .center)
        .opacity(dimReadState && content.isRead ? 0.85 : 1.0)
    }
}
