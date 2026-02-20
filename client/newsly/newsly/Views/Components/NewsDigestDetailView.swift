//
//  NewsDigestDetailView.swift
//  newsly
//
//  Created by Assistant on 9/23/25.
//

import SwiftUI

struct NewsDigestDetailView: View {
    let content: ContentDetail
    let metadata: NewsMetadata
    let onDiscussionTap: ((URL) -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            if let summary = metadata.summary {
                summarySection(summary: summary)
            }

            if let article = metadata.article {
                articleSection(article: article)
            }

            if let aggregator = metadata.aggregator {
                aggregatorSection(aggregator: aggregator)
            }
        }
    }

    @ViewBuilder
    private func summarySection(summary: NewsSummaryMetadata) -> some View {
        let hasOverview = summary.summary?.isEmpty == false
        let hasKeyPoints = !summary.keyPoints.isEmpty

        VStack(alignment: .leading, spacing: 16) {
            if hasOverview || hasKeyPoints {
                HStack {
                    Text("Summary")
                        .font(.headline)
                        .fontWeight(.semibold)

                    Spacer()

                    if let urlString = metadata.discussionURL,
                       let url = URL(string: urlString) {
                        Button(action: {
                            onDiscussionTap?(url)
                        }) {
                            Label("Comments", systemImage: "bubble.left.and.bubble.right")
                                .font(.caption)
                                .fontWeight(.medium)
                                .foregroundColor(.orange)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 5)
                                .background(Color.orange.opacity(0.1))
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
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
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)

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
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)

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

}
