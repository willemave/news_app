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
            // Run title — SectionHeader style
            VStack(alignment: .leading, spacing: 4) {
                Text(runTitle(for: run.runCreatedAt).uppercased())
                    .font(.sectionHeader)
                    .foregroundStyle(Color.textTertiary)
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
                suggestionCards(run.feeds, type: "feed")
            }

            if !run.podcasts.isEmpty {
                if !run.feeds.isEmpty {
                    sectionDivider
                }
                typeSectionHeader(title: "Podcasts", icon: "waveform", color: .orange, count: run.podcasts.count)
                suggestionCards(run.podcasts, type: "podcast_rss")
            }

            if !run.youtube.isEmpty {
                if !run.feeds.isEmpty || !run.podcasts.isEmpty {
                    sectionDivider
                }
                typeSectionHeader(title: "YouTube", icon: "play.rectangle.fill", color: .red, count: run.youtube.count)
                suggestionCards(run.youtube, type: "youtube")
            }
        }
    }

    private func typeSectionHeader(title: String, icon: String, color: Color, count: Int) -> some View {
        HStack(spacing: 10) {
            // Colored icon badge
            ZStack {
                Circle()
                    .fill(color.opacity(0.12))
                    .frame(width: 28, height: 28)
                Image(systemName: icon)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(color)
            }

            Text(title)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.primary)

            Text("\(count)")
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundColor(.secondary)
                .monospacedDigit()
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color(.tertiarySystemFill))
                .cornerRadius(4)

            Spacer()
        }
        .padding(.horizontal, Spacing.screenHorizontal)
        .padding(.top, 20)
        .padding(.bottom, 12)
    }

    private var sectionDivider: some View {
        Divider()
            .padding(.horizontal, Spacing.screenHorizontal)
            .padding(.top, 8)
    }

    private func suggestionCards(_ suggestions: [DiscoverySuggestion], type: String) -> some View {
        VStack(spacing: 10) {
            ForEach(suggestions) { suggestion in
                DiscoverySuggestionCard(
                    suggestion: suggestion,
                    suggestionType: suggestion.suggestionType.isEmpty ? type : suggestion.suggestionType,
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
