//
//  DiscoveryRunSection.swift
//  newsly
//

import SwiftUI

struct DiscoveryRunSection: View {
    let run: DiscoveryRunSuggestions
    let onSubscribe: (DiscoverySuggestion) -> Void
    let onAddItem: (DiscoverySuggestion) -> Void
    let onOpen: (DiscoverySuggestion) -> Void
    let onDismiss: (DiscoverySuggestion) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text(runTitle(for: run.runCreatedAt))
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
                    .textCase(.uppercase)
                    .tracking(0.5)

                if let summary = run.directionSummary, !summary.isEmpty {
                    Text(summary)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                        .truncationMode(.tail)
                        .padding(.top, 2)
                }
            }
            .padding(.horizontal, Spacing.screenHorizontal)
            .padding(.top, Spacing.sectionTop)
            .padding(.bottom, 16)

            if !run.feeds.isEmpty {
                typeSectionHeader(title: "Feeds", icon: "doc.text", color: .blue, count: run.feeds.count)
                suggestionCards(run.feeds)
            }

            if !run.podcasts.isEmpty {
                typeSectionHeader(title: "Podcasts", icon: "waveform", color: .orange, count: run.podcasts.count)
                suggestionCards(run.podcasts)
            }

            if !run.youtube.isEmpty {
                typeSectionHeader(title: "YouTube", icon: "play.rectangle.fill", color: .red, count: run.youtube.count)
                suggestionCards(run.youtube)
            }
        }
    }

    private func typeSectionHeader(title: String, icon: String, color: Color, count: Int) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .regular))
                .foregroundColor(.secondary)

            Text(title)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.primary)

            Text("\(count)")
                .font(.caption)
                .foregroundColor(.secondary)
                .monospacedDigit()

            Spacer()
        }
        .padding(.horizontal, Spacing.screenHorizontal)
        .padding(.top, 20)
        .padding(.bottom, 12)
    }

    private func suggestionCards(_ suggestions: [DiscoverySuggestion]) -> some View {
        VStack(spacing: 12) {
            ForEach(suggestions) { suggestion in
                DiscoverySuggestionCard(
                    suggestion: suggestion,
                    onSubscribe: { onSubscribe(suggestion) },
                    onAddItem: suggestion.hasItem ? { onAddItem(suggestion) } : nil,
                    onOpen: { onOpen(suggestion) },
                    onDismiss: { onDismiss(suggestion) }
                )
            }
        }
        .padding(.horizontal, Spacing.screenHorizontal)
    }

    private func runTitle(for dateString: String) -> String {
        guard let date = parseDate(dateString) else { return "Discovery" }
        let calendar = Calendar.current
        let startOfWeek = calendar.dateInterval(of: .weekOfYear, for: date)?.start ?? date
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return "Week of \(formatter.string(from: startOfWeek))"
    }

    private func parseDate(_ dateString: String) -> Date? {
        let iso8601WithFractional = ISO8601DateFormatter()
        iso8601WithFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso8601WithFractional.date(from: dateString) {
            return date
        }

        let iso8601 = ISO8601DateFormatter()
        iso8601.formatOptions = [.withInternetDateTime]
        return iso8601.date(from: dateString)
    }
}
