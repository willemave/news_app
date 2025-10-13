//
//  NewsGroupCard.swift
//  newsly
//
//  Created by Assistant on 10/12/25.
//

import SwiftUI

struct NewsGroupCard: View {
    let group: NewsGroup
    let onConvert: (Int) async -> Void

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
                HStack(alignment: .top, spacing: 12) {
                    // Content
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

                    Spacer()

                    // Convert icon button
                    Button(action: {
                        Task {
                            convertingStates[item.id] = true
                            await onConvert(item.id)
                            convertingStates[item.id] = false
                        }
                    }) {
                        Group {
                            if convertingStates[item.id] == true {
                                ProgressView()
                                    .scaleEffect(0.7)
                            } else {
                                Image(systemName: "arrow.right.circle")
                                    .font(.title3)
                                    .foregroundColor(.blue)
                            }
                        }
                        .frame(width: 28, height: 28)
                    }
                    .buttonStyle(.borderless)
                    .disabled(convertingStates[item.id] == true)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)

                if item.id != group.items.last?.id {
                    Divider()
                        .padding(.horizontal, 16)
                }
            }
            .padding(.bottom, 12)
        }
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.1), radius: 4, x: 0, y: 2)
        .opacity(group.isRead ? 0.7 : 1.0)
    }
}
