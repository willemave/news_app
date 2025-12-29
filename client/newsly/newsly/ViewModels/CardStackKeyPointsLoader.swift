//
//  CardStackKeyPointsLoader.swift
//  newsly
//
//  Prefetches ContentDetail to extract key points, hook, and topics for card stack display.
//

import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "CardStackKeyPointsLoader")

/// Cached data for a content card including key points, hook, and topics
struct CardPreviewData {
    let keyPoints: [String]
    let hook: String?
    let topics: [String]
}

@MainActor
class CardStackKeyPointsLoader: ObservableObject {
    @Published var cache: [Int: CardPreviewData] = [:]
    @Published var loadingIds: Set<Int> = []

    private let contentService = ContentService.shared

    func previewData(for contentId: Int) -> CardPreviewData? {
        cache[contentId]
    }

    func keyPoints(for contentId: Int) -> [String]? {
        cache[contentId]?.keyPoints
    }

    func hook(for contentId: Int) -> String? {
        cache[contentId]?.hook
    }

    func topics(for contentId: Int) -> [String]? {
        cache[contentId]?.topics
    }

    func isLoading(_ contentId: Int) -> Bool {
        loadingIds.contains(contentId)
    }

    func prefetch(contentIds: [Int], aroundIndex currentIndex: Int) async {
        guard !contentIds.isEmpty else { return }

        let indicesToFetch = [
            currentIndex - 1,
            currentIndex,
            currentIndex + 1,
            currentIndex + 2
        ].filter { $0 >= 0 && $0 < contentIds.count }

        for index in indicesToFetch {
            let contentId = contentIds[index]

            guard cache[contentId] == nil, !loadingIds.contains(contentId) else {
                continue
            }

            loadingIds.insert(contentId)

            do {
                let detail = try await contentService.fetchContentDetail(id: contentId)
                let points = detail.bulletPoints.map { $0.text }

                // Extract hook from interleaved summary if available
                let hook = detail.interleavedSummary?.hook

                // Get topics from content detail
                let topics = detail.topics

                cache[contentId] = CardPreviewData(
                    keyPoints: points,
                    hook: hook,
                    topics: topics
                )
                logger.debug("Fetched preview data for content \(contentId): \(points.count) points, hook: \(hook != nil), topics: \(topics.count)")
            } catch {
                logger.error("Failed to fetch preview data for \(contentId): \(error.localizedDescription)")
                cache[contentId] = CardPreviewData(keyPoints: [], hook: nil, topics: [])
            }

            loadingIds.remove(contentId)
        }
    }

    func clearCache() {
        cache.removeAll()
        loadingIds.removeAll()
    }
}
