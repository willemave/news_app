//
//  OnboardingSuggestionCard.swift
//  newsly
//
//  Extracted from OnboardingFlowView for reuse in DiscoveryPersonalizeSheet.
//

import SwiftUI

struct OnboardingSuggestionCard: View {
    let suggestion: OnboardingSuggestion
    let isSelected: Bool
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            VStack(alignment: .leading, spacing: 8) {
                // Metadata bar
                HStack(spacing: 6) {
                    Image(systemName: typeIcon)
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(typeAccentColor)

                    Text(sourceLabel.uppercased())
                        .font(.editorialMeta)
                        .foregroundColor(.editorialSub)
                        .tracking(0.5)
                        .lineLimit(1)

                    Spacer()

                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.body)
                        .foregroundColor(isSelected ? .watercolorSlate : Color(.tertiaryLabel))
                }

                // Headline
                Text(suggestion.displayTitle)
                    .font(.editorialHeadline)
                    .foregroundColor(.watercolorSlate)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)

                // Rationale
                if let rationale = suggestion.rationale, !rationale.isEmpty {
                    Text(rationale)
                        .font(.caption)
                        .foregroundColor(.watercolorSlate.opacity(0.6))
                        .lineLimit(2)
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white.opacity(isSelected ? 0.6 : 0.35))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.editorialBorder, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(EditorialCardButtonStyle())
    }

    private var typeIcon: String {
        switch suggestion.suggestionType {
        case "substack", "newsletter": return "envelope.open"
        case "podcast_rss", "podcast": return "waveform"
        case "reddit": return "bubble.left.and.text.bubble.right"
        default: return "doc.text"
        }
    }

    private var typeAccentColor: Color {
        switch suggestion.suggestionType {
        case "substack", "newsletter": return .blue
        case "podcast_rss", "podcast": return .orange
        case "reddit": return .purple
        default: return .blue
        }
    }

    private var sourceLabel: String {
        switch suggestion.suggestionType {
        case "substack", "newsletter": return "Newsletter"
        case "podcast_rss", "podcast": return "Podcast"
        case "reddit": return "Reddit"
        default: return "Feed"
        }
    }
}
