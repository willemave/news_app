//
//  NewsDigestDetailView.swift
//  newsly
//
//  Created by Assistant on 9/23/25.
//

import MarkdownUI
import SwiftUI

struct NewsDigestDetailView: View {
    let content: ContentDetail
    let metadata: NewsMetadata

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if let summary = metadata.summary {
                summarySection(summary: summary)
            }

            if let article = metadata.article {
                articleSection(article: article)
            }

            if let aggregator = metadata.aggregator {
                aggregatorSection(aggregator: aggregator)
            }

            legacyFallbackSection
        }
    }

    @ViewBuilder
    private func summarySection(summary: NewsSummaryMetadata) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("Digest Summary")
                    .font(.title2)
                    .fontWeight(.semibold)

                if let classification = summary.classification {
                    Text(classification.localizedCapitalized)
                        .font(.caption)
                        .fontWeight(.medium)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(chipColor(for: classification))
                        .foregroundColor(.white)
                        .clipShape(Capsule())
                }
            }

            if let summarizationDate = summary.summarizationDate,
               let formatted = formatDate(summarizationDate) {
                Text("Generated \(formatted)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if let overview = summary.summary, !overview.isEmpty {
                Text(overview)
                    .font(.body)
            }

            if !summary.keyPoints.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Key Points")
                        .font(.headline)

                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(summary.keyPoints.enumerated()), id: \.offset) { index, point in
                            HStack(alignment: .top, spacing: 8) {
                                Image(systemName: "circle.fill")
                                    .font(.system(size: 6))
                                    .padding(.top, 6)
                                Text(point)
                                    .font(.callout)
                                    .foregroundColor(.primary)
                                    .multilineTextAlignment(.leading)
                            }
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel("Key point \(index + 1): \(point)")
                        }
                    }
                }
            }

            if let articleURLString = summary.articleURL,
               let articleURL = URL(string: articleURLString) {
                let linkTitle = summary.title ?? content.displayTitle
                Link(destination: articleURL) {
                    HStack(spacing: 6) {
                        Image(systemName: "link")
                        Text(linkTitle)
                            .lineLimit(2)
                    }
                }
                .font(.footnote)
                .foregroundColor(.blue)
            }
        }
        .padding()
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(12)
    }

    @ViewBuilder
    private func articleSection(article: NewsArticleMetadata) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Linked Article")
                .font(.headline)
                .fontWeight(.semibold)

            if let sourceDomain = article.sourceDomain {
                Text(sourceDomain)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if let title = article.title, let urlString = article.url, let url = URL(string: urlString) {
                Link(destination: url) {
                    Text(title)
                        .font(.body)
                        .multilineTextAlignment(.leading)
                }
            } else if let urlString = article.url, let url = URL(string: urlString) {
                Link(destination: url) {
                    Text(urlString)
                        .font(.body)
                        .lineLimit(2)
                }
            }
        }
        .padding()
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(12)
    }

    @ViewBuilder
    private func aggregatorSection(aggregator: NewsAggregatorMetadata) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Aggregator")
                .font(.headline)
                .fontWeight(.semibold)

            if let name = aggregator.name {
                Text(name)
                    .font(.subheadline)
                    .fontWeight(.medium)
            }

            if let feedName = aggregator.feedName {
                Text(feedName)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if let title = aggregator.title {
                Text(title)
                    .font(.callout)
                    .foregroundColor(.primary)
            }

            if let summaryText = aggregator.summaryText {
                Text(summaryText)
                    .font(.callout)
                    .foregroundColor(.secondary)
            }

            if let urlString = aggregator.url, let url = URL(string: urlString) {
                Link("Open discussion", destination: url)
                    .font(.footnote)
            }

            if !aggregator.relatedLinks.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Related links")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    ForEach(aggregator.relatedLinks) { link in
                        if let url = URL(string: link.url) {
                            Link(link.title ?? link.url, destination: url)
                                .font(.footnote)
                                .foregroundColor(.blue)
                                .lineLimit(2)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(12)
    }

    @ViewBuilder
    private var legacyFallbackSection: some View {
        if let markdown = content.renderedMarkdown, !markdown.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Text("Full Digest")
                    .font(.headline)
                    .fontWeight(.semibold)

                Markdown(markdown)
                    .markdownTheme(.gitHub)
            }
            .padding()
            .background(Color(UIColor.secondarySystemBackground))
            .cornerRadius(12)
        } else if let items = content.newsItems, !items.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Updates")
                    .font(.headline)
                    .fontWeight(.semibold)

                VStack(alignment: .leading, spacing: 10) {
                    ForEach(items) { item in
                        VStack(alignment: .leading, spacing: 6) {
                            if let url = URL(string: item.url) {
                                Link(item.title ?? item.url, destination: url)
                                    .font(.subheadline)
                            } else {
                                Text(item.title ?? item.url)
                                    .font(.subheadline)
                            }

                            if let summary = item.summary, !summary.isEmpty {
                                Text(summary)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        Divider()
                    }
                }
            }
            .padding()
            .background(Color(UIColor.secondarySystemBackground))
            .cornerRadius(12)
        }
    }

    private func chipColor(for classification: String) -> Color {
        switch classification.lowercased() {
        case "skip":
            return .gray
        default:
            return .blue
        }
    }

    private func formatDate(_ isoString: String) -> String? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        var date = formatter.date(from: isoString)
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: isoString)
        }

        guard let parsed = date else { return nil }

        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        return displayFormatter.string(from: parsed)
    }
}
