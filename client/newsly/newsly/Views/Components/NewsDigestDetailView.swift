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
            if summaryText != nil || !keyPoints.isEmpty {
                summarySection()
            }

            if hasArticleSection {
                articleSection()
            }

            if hasAggregatorSection {
                aggregatorSection()
            }
        }
    }

    private var summaryText: String? {
        content.resolvedNewsSummaryText
    }

    private var keyPoints: [String] {
        content.resolvedNewsKeyPoints
    }

    private var discussionURL: URL? {
        let rawURL = normalizedText(content.newsDiscussionURL) ?? normalizedText(metadata.discussionURL)
        guard let rawURL else { return nil }
        return URL(string: rawURL)
    }

    private var articleTitle: String? {
        guard let title = normalizedText(metadata.article?.title) else { return nil }
        if isDuplicate(title, comparedTo: content.displayTitle) || isDuplicate(title, comparedTo: summaryText) {
            return nil
        }
        return title
    }

    private var articleURL: URL? {
        let rawURL = normalizedText(metadata.article?.url) ?? normalizedText(content.newsArticleURL)
        guard let rawURL else { return nil }
        return URL(string: rawURL)
    }

    private var articleSourceDomain: String? {
        guard articleTitle != nil || articleURL != nil else { return nil }
        return normalizedText(metadata.article?.sourceDomain)
    }

    private var hasArticleSection: Bool {
        articleTitle != nil || articleURL != nil
    }

    private var aggregatorName: String? {
        normalizedText(metadata.aggregator?.name)
    }

    private var aggregatorFeedName: String? {
        normalizedText(metadata.aggregator?.feedName)
    }

    private var aggregatorTitle: String? {
        guard let title = normalizedText(metadata.aggregator?.title) else { return nil }
        if isDuplicate(title, comparedTo: content.displayTitle)
            || isDuplicate(title, comparedTo: articleTitle)
            || isDuplicate(title, comparedTo: summaryText) {
            return nil
        }
        return title
    }

    private var aggregatorSummaryText: String? {
        guard let text = normalizedText(metadata.aggregator?.summaryText) else { return nil }
        if isDuplicate(text, comparedTo: summaryText)
            || isDuplicate(text, comparedTo: aggregatorTitle)
            || isDuplicate(text, comparedTo: articleTitle) {
            return nil
        }
        return text
    }

    private var relatedLinks: [NewsRelatedLink] {
        guard let aggregator = metadata.aggregator else { return [] }

        let excludedURLs = Set(
            [
                normalizedURLKey(metadata.article?.url),
                normalizedURLKey(content.newsArticleURL),
                normalizedURLKey(content.newsDiscussionURL),
                normalizedURLKey(metadata.discussionURL),
            ].compactMap { $0 }
        )

        var seen: Set<String> = []
        var result: [NewsRelatedLink] = []

        for link in aggregator.relatedLinks {
            let urlKey = normalizedURLKey(link.url) ?? link.url.lowercased()
            guard !excludedURLs.contains(urlKey) else { continue }
            if seen.insert(urlKey).inserted {
                result.append(link)
            }
        }

        return result
    }

    private var hasAggregatorSection: Bool {
        aggregatorName != nil
            || aggregatorFeedName != nil
            || aggregatorTitle != nil
            || aggregatorSummaryText != nil
            || !relatedLinks.isEmpty
    }

    @ViewBuilder
    private func summarySection() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Summary")
                    .font(.headline)
                    .fontWeight(.semibold)

                Spacer()

                if let url = discussionURL {
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

            if let overview = summaryText {
                Text(overview)
                    .font(.callout)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if !keyPoints.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Key Points")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)

                    ForEach(Array(keyPoints.enumerated()), id: \.offset) { _, point in
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
    private func articleSection() -> some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Linked Article")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)

                if let sourceDomain = articleSourceDomain {
                    Text(sourceDomain)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            if let title = articleTitle, let url = articleURL {
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
            } else if let url = articleURL {
                Link(destination: url) {
                    HStack(spacing: 8) {
                        Image(systemName: "arrow.up.right.square")
                            .font(.callout)
                        Text(url.absoluteString)
                            .font(.callout)
                            .lineLimit(2)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func aggregatorSection() -> some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Aggregator")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)

                if let name = aggregatorName {
                    Text(name)
                        .font(.subheadline)
                        .fontWeight(.medium)
                }

                if let feedName = aggregatorFeedName {
                    Text(feedName)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            if let title = aggregatorTitle {
                Text(title)
                    .font(.callout)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let summaryText = aggregatorSummaryText {
                Text(summaryText)
                    .font(.callout)
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if !relatedLinks.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Related Links")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)

                    ForEach(relatedLinks) { link in
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

    private func normalizedText(_ value: String?) -> String? {
        guard let value else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func normalizedURLKey(_ value: String?) -> String? {
        normalizedText(value)?.lowercased()
    }

    private func normalizedComparisonKey(_ value: String?) -> String? {
        guard let value = normalizedText(value)?.lowercased() else { return nil }
        let transformed = value.unicodeScalars.map { scalar -> String in
            CharacterSet.alphanumerics.contains(scalar) ? String(scalar) : " "
        }
        let collapsed = transformed.joined()
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: " ")
        return collapsed.isEmpty ? nil : collapsed
    }

    private func isDuplicate(_ lhs: String?, comparedTo rhs: String?) -> Bool {
        guard let left = normalizedComparisonKey(lhs), let right = normalizedComparisonKey(rhs) else {
            return false
        }
        return left == right || left.contains(right) || right.contains(left)
    }

}
