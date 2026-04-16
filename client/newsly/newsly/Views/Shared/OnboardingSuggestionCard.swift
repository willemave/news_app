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
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundColor(isSelected ? .watercolorSlate : Color(.tertiaryLabel))

                VStack(alignment: .leading, spacing: 2) {
                    Text(suggestion.displayTitle)
                        .font(.subheadline.weight(.medium))
                        .foregroundColor(.watercolorSlate)
                        .lineLimit(1)

                    if let rationale = suggestion.rationale, !rationale.isEmpty {
                        Text(rationale)
                            .font(.caption)
                            .foregroundColor(.watercolorSlate.opacity(0.55))
                            .lineLimit(1)
                    }
                }

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.watercolorSlate.opacity(isSelected ? 0.1 : 0.05))
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color.watercolorSlate.opacity(isSelected ? 0.2 : 0.12), lineWidth: 1)
            )
        }
        .buttonStyle(EditorialCardButtonStyle())
        .accessibilityIdentifier("onboarding.suggestion.\(suggestion.stableKey)")
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
