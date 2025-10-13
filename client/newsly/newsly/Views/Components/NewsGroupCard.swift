//
//  NewsGroupCard.swift
//  newsly
//
//  Created by Assistant on 10/12/25.
//

import SwiftUI

struct NewsGroupCard: View {
    let group: NewsGroup
    let onMarkAllAsRead: () async -> Void
    let onToggleFavorite: (Int) async -> Void
    let onConvert: (Int) async -> Void

    @State private var isMarkingAll = false
    @State private var favoriteStates: [Int: Bool] = [:]
    @State private var convertingStates: [Int: Bool] = [:]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Group header with count
            HStack {
                Text("News Digest")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)

                Spacer()

                Text("\(group.items.count) items")
                    .font(.caption2)
                    .foregroundColor(.secondary)

                if group.isRead {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundColor(.green)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)

            // News items
            ForEach(group.items) { item in
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.displayTitle)
                        .font(.subheadline)
                        .foregroundColor(item.isRead ? .secondary : .primary)
                        .lineLimit(2)

                    HStack(spacing: 6) {
                        PlatformIcon(platform: item.platform)
                            .opacity(item.platform == nil ? 0 : 1)
                        if let source = item.source {
                            Text(source)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 4)

                if item.id != group.items.last?.id {
                    Divider()
                        .padding(.horizontal, 16)
                }
            }

            // Action buttons
            HStack(spacing: 16) {
                // Favorite button
                Button(action: {
                    Task {
                        if let firstItemId = group.items.first?.id {
                            await onToggleFavorite(firstItemId)
                        }
                    }
                }) {
                    HStack {
                        Image(systemName: group.items.first?.isFavorited == true ? "star.fill" : "star")
                        Text("Favorite")
                    }
                    .font(.subheadline)
                    .foregroundColor(.blue)
                }
                .buttonStyle(.borderless)
                .frame(maxWidth: .infinity)

                Divider()
                    .frame(height: 20)

                // Convert button
                Button(action: {
                    Task {
                        if let firstItemId = group.items.first?.id {
                            convertingStates[firstItemId] = true
                            await onConvert(firstItemId)
                            convertingStates[firstItemId] = false
                        }
                    }
                }) {
                    HStack {
                        if convertingStates[group.items.first?.id ?? 0] == true {
                            ProgressView()
                                .scaleEffect(0.8)
                        } else {
                            Image(systemName: "arrow.right.circle")
                        }
                        Text("Convert")
                    }
                    .font(.subheadline)
                    .foregroundColor(.blue)
                }
                .buttonStyle(.borderless)
                .frame(maxWidth: .infinity)
                .disabled(convertingStates[group.items.first?.id ?? 0] == true)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 12)
            .padding(.top, 8)
        }
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.1), radius: 4, x: 0, y: 2)
        .opacity(group.isRead ? 0.7 : 1.0)
    }
}
