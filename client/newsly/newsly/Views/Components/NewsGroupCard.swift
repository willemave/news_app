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

    /// Format publication date for compact display
    private func formatDateShort(_ dateString: String) -> String {
        let iso8601WithFractional = ISO8601DateFormatter()
        iso8601WithFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        if let date = iso8601WithFractional.date(from: dateString) {
            let now = Date()
            let calendar = Calendar.current
            let components = calendar.dateComponents([.day, .hour], from: date, to: now)

            if let days = components.day, days == 0 {
                if let hours = components.hour {
                    return "\(hours)h ago"
                }
            } else if let days = components.day, days < 7 {
                return "\(days)d ago"
            }

            let formatter = DateFormatter()
            formatter.dateFormat = "MMM d"
            return formatter.string(from: date)
        }

        return ""
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Group header
            HStack {
                Text("News Digest")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(.secondary)

                Spacer()

                if group.isRead {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.caption2)
                        .foregroundColor(.green)
                }
            }
            .padding(.horizontal, 4)
            .padding(.top, 4)

            // News items
            ForEach(group.items) { item in
                NavigationLink(destination: ContentDetailView(contentId: item.id, allContentIds: group.items.map { $0.id })) {
                    HStack(alignment: .top, spacing: 10) {
                        // Content
                        VStack(alignment: .leading, spacing: 2) {
                            // Title - full display
                            Text(item.displayTitle)
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundColor(item.isRead ? .secondary : .primary)
                                .fixedSize(horizontal: false, vertical: true)

                            // Short summary if available
                            if let summary = item.shortSummary, !summary.isEmpty {
                                Text(summary)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                                    .lineLimit(2)
                            }

                            // Metadata row
                            HStack(spacing: 6) {
                                // Platform icon and source
                                HStack(spacing: 3) {
                                    PlatformIcon(platform: item.platform)
                                        .opacity(item.platform == nil ? 0 : 1)
                                    if let source = item.source {
                                        Text(source)
                                            .font(.caption2)
                                            .foregroundColor(.secondary)
                                            .lineLimit(1)
                                    }
                                }

                                Spacer()

                                // Date
                                if let pubDate = item.publicationDate {
                                    Text(formatDateShort(pubDate))
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }

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
                                        .scaleEffect(0.6)
                                } else {
                                    Image(systemName: "arrow.right.circle")
                                        .font(.body)
                                        .foregroundColor(.blue)
                                }
                            }
                            .frame(width: 24, height: 24)
                        }
                        .buttonStyle(.borderless)
                        .disabled(convertingStates[item.id] == true)
                    }
                    .padding(.horizontal, 4)
                    .padding(.vertical, 6)
                }
                .buttonStyle(.plain)

                if item.id != group.items.last?.id {
                    Divider()
                        .padding(.horizontal, 4)
                }
            }
            .padding(.bottom, 4)
        }
        .opacity(group.isRead ? 0.7 : 1.0)
    }
}
