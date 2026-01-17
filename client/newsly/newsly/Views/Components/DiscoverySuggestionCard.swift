//
//  DiscoverySuggestionCard.swift
//  newsly
//

import SwiftUI

struct DiscoverySuggestionCard: View {
    let suggestion: DiscoverySuggestion
    let onSubscribe: () -> Void
    let onAddItem: (() -> Void)?
    let onOpen: () -> Void
    let onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Text(suggestion.displayTitle)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)

                if let subtitle = suggestion.displaySubtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }

                HStack(spacing: 0) {
                    HStack(spacing: 4) {
                        Image(systemName: "link")
                            .font(.system(size: 10))
                        Text(formattedURL(suggestion.primaryURL))
                            .lineLimit(1)
                    }
                    .font(.caption2)
                    .foregroundColor(Color(.tertiaryLabel))

                    Spacer()

                    HStack(spacing: 16) {
                        if suggestion.canSubscribe {
                            Button(action: onSubscribe) {
                                Image(systemName: "plus")
                                    .font(.system(size: 16, weight: .regular))
                                    .foregroundColor(.accentColor)
                            }
                        }

                        if let onAddItem {
                            Button(action: onAddItem) {
                                Image(systemName: "arrow.down")
                                    .font(.system(size: 16, weight: .regular))
                                    .foregroundColor(.secondary)
                            }
                        }

                        Button(action: onOpen) {
                            Image(systemName: "safari")
                                .font(.system(size: 16, weight: .regular))
                                .foregroundColor(.secondary)
                        }

                        Button(action: onDismiss) {
                            Image(systemName: "xmark")
                                .font(.system(size: 14, weight: .regular))
                                .foregroundColor(Color(.tertiaryLabel))
                        }
                    }
                }
                .padding(.top, 4)
            }
            .padding(16)
        }
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(12)
    }

    private func formattedURL(_ urlString: String) -> String {
        guard let url = URL(string: urlString),
              let host = url.host else {
            return urlString
        }
        return host.replacingOccurrences(of: "www.", with: "")
    }
}
