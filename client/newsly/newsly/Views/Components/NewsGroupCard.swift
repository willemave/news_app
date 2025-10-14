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
                    VStack(alignment: .leading, spacing: 6) {
                        // Title - full text, no line limit
                        Text(item.displayTitle)
                            .font(.body)
                            .fontWeight(.medium)
                            .foregroundColor(item.isRead ? .secondary : .primary)
                            .fixedSize(horizontal: false, vertical: true)

                        // Short summary if available
                        if let summary = item.shortSummary, !summary.isEmpty {
                            Text(summary)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(2)
                        }

                        // Metadata row
                        HStack(spacing: 8) {
                            // Platform icon and source
                            HStack(spacing: 4) {
                                PlatformIcon(platform: item.platform)
                                    .opacity(item.platform == nil ? 0 : 1)
                                if let source = item.source {
                                    Text(source)
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                        .lineLimit(1)
                                }
                            }

                            // Classification badge
                            if let classification = item.classification {
                                Text(classification)
                                    .font(.caption2)
                                    .foregroundColor(.white)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(Color.blue.opacity(0.7))
                                    .cornerRadius(4)
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
                .padding(.vertical, 12)

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
