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
        VStack(alignment: .leading, spacing: 24) {
            if let summary = metadata.summary {
                summarySection(summary: summary)
            }

            if let article = metadata.article {
                Divider()
                    .padding(.vertical, 4)
                articleSection(article: article)
            }

            if let aggregator = metadata.aggregator {
                Divider()
                    .padding(.vertical, 4)
                aggregatorSection(aggregator: aggregator)
            }

            legacyFallbackSection
        }
    }

    @ViewBuilder
    private func summarySection(summary: NewsSummaryMetadata) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Digest Summary")
                    .font(.title2)
                    .fontWeight(.bold)

                if let summarizationDate = summary.summarizationDate,
                   let formatted = formatDate(summarizationDate) {
                    Text("Generated \(formatted)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            if let overview = summary.summary, !overview.isEmpty {
                Text(overview)
                    .font(.body)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if !summary.keyPoints.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Key Points")
                        .font(.headline)

                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(Array(summary.keyPoints.enumerated()), id: \.offset) { index, point in
                            HStack(alignment: .top, spacing: 12) {
                                Circle()
                                    .fill(Color.accentColor)
                                    .frame(width: 6, height: 6)
                                    .padding(.top, 7)

                                Text(point)
                                    .font(.body)
                                    .fixedSize(horizontal: false, vertical: true)
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
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.up.right.square")
                        Text(linkTitle)
                            .lineLimit(2)
                    }
                }
                .font(.callout)
            }
        }
    }

    @ViewBuilder
    private func articleSection(article: NewsArticleMetadata) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Linked Article")
                    .font(.headline)
                    .fontWeight(.semibold)

                if let sourceDomain = article.sourceDomain {
                    Text(sourceDomain)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            if let title = article.title, let urlString = article.url, let url = URL(string: urlString) {
                Link(destination: url) {
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.up.right.square")
                            .font(.body)
                        Text(title)
                            .font(.body)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            } else if let urlString = article.url, let url = URL(string: urlString) {
                Link(destination: url) {
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.up.right.square")
                            .font(.body)
                        Text(urlString)
                            .font(.body)
                            .lineLimit(2)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func aggregatorSection(aggregator: NewsAggregatorMetadata) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
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
            }

            if let title = aggregator.title {
                Text(title)
                    .font(.body)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let summaryText = aggregator.summaryText {
                Text(summaryText)
                    .font(.body)
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let urlString = aggregator.url, let url = URL(string: urlString) {
                Link(destination: url) {
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.up.right.square")
                        Text("Open discussion")
                    }
                }
                .font(.callout)
            }

            if !aggregator.relatedLinks.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Related Links")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)

                    ForEach(aggregator.relatedLinks) { link in
                        if let url = URL(string: link.url) {
                            Link(destination: url) {
                                HStack(spacing: 8) {
                                    Image(systemName: "link")
                                        .font(.caption)
                                    Text(link.title ?? link.url)
                                        .font(.callout)
                                        .lineLimit(2)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var legacyFallbackSection: some View {
        if let markdown = content.renderedMarkdown, !markdown.isEmpty {
            Divider()
                .padding(.vertical, 8)

            VStack(alignment: .leading, spacing: 12) {
                Text("Full Digest")
                    .font(.title2)
                    .fontWeight(.bold)

                Markdown(markdown)
                    .markdownTheme(.gitHub)
            }
        } else if let items = content.newsItems, !items.isEmpty {
            Divider()
                .padding(.vertical, 8)

            VStack(alignment: .leading, spacing: 16) {
                Text("Updates")
                    .font(.title2)
                    .fontWeight(.bold)

                VStack(alignment: .leading, spacing: 16) {
                    ForEach(items) { item in
                        VStack(alignment: .leading, spacing: 8) {
                            if let url = URL(string: item.url) {
                                Link(destination: url) {
                                    HStack(spacing: 8) {
                                        Image(systemName: "arrow.up.right.square")
                                            .font(.body)
                                        Text(item.title ?? item.url)
                                            .font(.body)
                                            .fontWeight(.medium)
                                    }
                                }
                            } else {
                                Text(item.title ?? item.url)
                                    .font(.body)
                                    .fontWeight(.medium)
                            }

                            if let summary = item.summary, !summary.isEmpty {
                                Text(summary)
                                    .font(.body)
                                    .foregroundColor(.secondary)
                            }
                        }

                        if item.id != items.last?.id {
                            Divider()
                                .padding(.vertical, 4)
                        }
                    }
                }
            }
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
