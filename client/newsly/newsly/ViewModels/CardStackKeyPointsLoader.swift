//
//  CardStackKeyPointsLoader.swift
//  newsly
//
//  Prefetches ContentDetail to extract key points for card stack display.
//

import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "CardStackKeyPointsLoader")

@MainActor
class CardStackKeyPointsLoader: ObservableObject {
    @Published var cache: [Int: [String]] = [:]
    @Published var loadingIds: Set<Int> = []

    private let contentService = ContentService.shared

    func keyPoints(for contentId: Int) -> [String]? {
        cache[contentId]
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
                cache[contentId] = points
                logger.debug("Fetched \(points.count) key points for content \(contentId)")
            } catch {
                logger.error("Failed to fetch key points for \(contentId): \(error.localizedDescription)")
                cache[contentId] = []
            }

            loadingIds.remove(contentId)
        }
    }

    func clearCache() {
        cache.removeAll()
        loadingIds.removeAll()
    }
}
