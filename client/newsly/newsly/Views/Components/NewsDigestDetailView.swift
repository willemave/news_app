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
            // Discussion link at the top for quick access
            if let aggregator = metadata.aggregator,
               let urlString = aggregator.url,
               let url = URL(string: urlString) {
                discussionLink(url: url, aggregatorName: aggregator.name)
            }

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
    private func discussionLink(url: URL, aggregatorName: String?) -> some View {
        Link(destination: url) {
            HStack(spacing: 10) {
                Image(systemName: "bubble.left.and.bubble.right.fill")
                    .font(.body)
                    .foregroundColor(.orange)
                Text("Join the discussion")
                    .font(.callout)
                    .fontWeight(.medium)
                Spacer()
                Image(systemName: "arrow.up.right")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(Color(.systemBackground))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.orange.opacity(0.28), lineWidth: 1)
            )
            .cornerRadius(12)
        }
    }

    @ViewBuilder
    private func summarySection(summary: NewsSummaryMetadata) -> some View {
        let hasOverview = summary.summary?.isEmpty == false
        let hasKeyPoints = !summary.keyPoints.isEmpty

        VStack(alignment: .leading, spacing: 16) {
            if hasOverview || hasKeyPoints {
                Text("Summary")
                    .font(.headline)
                    .fontWeight(.semibold)
            }

            if let overview = summary.summary, !overview.isEmpty {
                Text(overview)
                    .font(.callout)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if hasKeyPoints {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Key Points")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)

                    ForEach(Array(summary.keyPoints.enumerated()), id: \.offset) { _, point in
                        HStack(alignment: .top, spacing: 12) {
                            Circle()
                                .fill(Color.accentColor.opacity(0.85))
                                .frame(width: 6, height: 6)
                                .padding(.top, 7)

                            Text(point)
                                .font(.callout)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
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
                            .font(.callout)
                        Text(title)
                            .font(.callout)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            } else if let urlString = article.url, let url = URL(string: urlString) {
                Link(destination: url) {
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.up.right.square")
                            .font(.callout)
                        Text(urlString)
                            .font(.callout)
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
                    .font(.callout)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let summaryText = aggregator.summaryText {
                Text(summaryText)
                    .font(.callout)
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
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
                                            .font(.callout)
                                        Text(item.title ?? item.url)
                                            .font(.callout)
                                            .fontWeight(.medium)
                                    }
                                }
                            } else {
                                Text(item.title ?? item.url)
                                    .font(.callout)
                                    .fontWeight(.medium)
                            }

                            if let summary = item.summary, !summary.isEmpty {
                                Text(summary)
                                    .font(.callout)
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

}
