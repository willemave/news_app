//
//  DiscoverySuggestionCard.swift
//  newsly
//

import SwiftUI

struct DiscoverySuggestionCard: View {
    let suggestion: DiscoverySuggestion
    let suggestionType: String
    let onSubscribe: () -> Void
    let onAddItem: (() -> Void)?
    let onOpen: () -> Void
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 0) {
            // Leading accent strip
            RoundedRectangle(cornerRadius: 1.5)
                .fill(accentColor)
                .frame(width: 3)
                .padding(.vertical, 12)

            VStack(alignment: .leading, spacing: 10) {
                // Title + dismiss
                HStack(alignment: .top, spacing: 8) {
                    Text(suggestion.displayTitle)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)

                    Spacer()

                    Button(action: onDismiss) {
                        Image(systemName: "xmark")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(Color.textTertiary)
                            .frame(width: 24, height: 24)
                    }
                    .buttonStyle(.plain)
                }

                // Subtitle
                if let subtitle = suggestion.displaySubtitle, subtitle != suggestion.rationale {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }

                // Rationale row
                if let rationale = suggestion.rationale, !rationale.isEmpty {
                    HStack(spacing: 5) {
                        Image(systemName: "sparkles")
                            .font(.system(size: 10, weight: .medium))
                            .foregroundColor(accentColor)
                        Text(rationale)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                            .lineLimit(2)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(accentColor.opacity(0.08))
                    .cornerRadius(6)
                }

                // URL + score row
                HStack(spacing: 0) {
                    HStack(spacing: 4) {
                        Image(systemName: "link")
                            .font(.system(size: 10))
                        Text(formattedURL(suggestion.primaryURL))
                            .lineLimit(1)
                    }
                    .font(.caption2)
                    .foregroundColor(Color.textTertiary)

                    Spacer()

                    if let score = suggestion.score, score > 0 {
                        Text("\(Int(score * 100))% match")
                            .font(.system(size: 10, weight: .medium, design: .rounded))
                            .foregroundColor(accentColor)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(accentColor.opacity(0.1))
                            .cornerRadius(4)
                    }
                }

                // Action buttons
                HStack(spacing: 8) {
                    if suggestion.canSubscribe {
                        Button(action: onSubscribe) {
                            Label("Subscribe", systemImage: "plus")
                                .font(.caption)
                                .fontWeight(.medium)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                        .tint(accentColor)
                    }

                    if let onAddItem {
                        Button(action: onAddItem) {
                            Label(suggestion.addItemLabel, systemImage: "arrow.down")
                                .font(.caption)
                                .fontWeight(.medium)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                    }

                    Button(action: onOpen) {
                        Label("Open", systemImage: "safari")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                    .controlSize(.small)

                    Spacer()
                }
            }
            .padding(.leading, 12)
            .padding(.trailing, 14)
            .padding(.vertical, 14)
        }
        .background(Color(.secondarySystemGroupedBackground))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.primary.opacity(0.06), lineWidth: 1)
        )
        .cornerRadius(12)
    }

    private var accentColor: Color {
        switch suggestionType {
        case "feed", "rss":
            return .blue
        case "podcast_rss", "podcast":
            return .orange
        case "youtube":
            return .red
        default:
            return .blue
        }
    }

    private func formattedURL(_ urlString: String) -> String {
        guard let url = URL(string: urlString),
              let host = url.host else {
            return urlString
        }
        return host.replacingOccurrences(of: "www.", with: "")
    }
}
