//
//  SourceRow.swift
//  newsly
//
//  Row component for feed and podcast sources with status chip.
//

import SwiftUI

struct SourceRow: View {
    let name: String
    let url: String?
    let type: String
    let isActive: Bool

    var body: some View {
        HStack(spacing: 12) {
            // Type icon
            SourceTypeIcon(type: type)

            // Content
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.listTitle)
                    .foregroundStyle(Color.textPrimary)
                    .lineLimit(1)

                if let url {
                    Text(formattedURL(url))
                        .font(.listMono)
                        .foregroundStyle(Color.textTertiary)
                        .lineLimit(1)
                }
            }

            Spacer(minLength: 8)

            // Status + chevron
            HStack(spacing: 8) {
                StatusChip(isActive: isActive)

                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color.textTertiary)
            }
        }
        .padding(.vertical, Spacing.rowVertical)
        .padding(.horizontal, Spacing.rowHorizontal)
        .contentShape(Rectangle())
    }

    private func formattedURL(_ urlString: String) -> String {
        guard let url = URL(string: urlString), let host = url.host else {
            return urlString
        }
        return host.replacingOccurrences(of: "www.", with: "")
    }
}

// MARK: - Source Type Icon

struct SourceTypeIcon: View {
    let type: String

    private var iconName: String {
        switch type.lowercased() {
        case "podcast_rss", "podcast":
            return "waveform"
        case "youtube":
            return "play.rectangle.fill"
        case "substack":
            return "newspaper"
        case "atom", "rss":
            return "dot.radiowaves.left.and.right"
        default:
            return "list.bullet.rectangle"
        }
    }

    private var iconColor: Color {
        switch type.lowercased() {
        case "podcast_rss", "podcast":
            return .purple
        case "youtube":
            return .red
        case "substack":
            return .orange
        default:
            return .blue
        }
    }

    var body: some View {
        Image(systemName: iconName)
            .font(.system(size: 17, weight: .medium))
            .foregroundStyle(iconColor)
            .frame(width: Spacing.iconSize, height: Spacing.iconSize)
    }
}

#Preview {
    VStack(spacing: 0) {
        SourceRow(
            name: "Stratechery",
            url: "https://stratechery.com/feed",
            type: "substack",
            isActive: true
        )

        Divider().padding(.leading, 56)

        SourceRow(
            name: "The Vergecast",
            url: "https://feeds.megaphone.fm/vergecast",
            type: "podcast_rss",
            isActive: true
        )

        Divider().padding(.leading, 56)

        SourceRow(
            name: "MKBHD",
            url: "https://youtube.com/mkbhd",
            type: "youtube",
            isActive: false
        )
    }
    .background(Color.surfacePrimary)
}
