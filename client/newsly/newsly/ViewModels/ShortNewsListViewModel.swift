//
//  ShortNewsListViewModel.swift
//  newsly
//
//  Created by Assistant on 3/16/26.
//

import Combine
import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "ShortNewsList")

@MainActor
final class ShortNewsListViewModel: BaseContentListViewModel {
    private let readRepository: ReadStatusRepositoryType
    private let unreadCountService: UnreadCountService

    private let itemsToMarkRead = PassthroughSubject<[Int], Never>()
    private var readCancellables = Set<AnyCancellable>()

    init(
        repository: ContentRepositoryType,
        readRepository: ReadStatusRepositoryType,
        unreadCountService: UnreadCountService
    ) {
        self.readRepository = readRepository
        self.unreadCountService = unreadCountService
        super.init(
            repository: repository,
            contentTypes: [.news],
            readFilter: .unread
        )
        bindReadTracking()
        bindReadStatusNotifications()
        logger.info("[ShortNewsList] ViewModel initialized")
    }

    /// Called when items have scrolled past the top of the screen
    func itemsScrolledPastTop(ids: [Int]) {
        guard !ids.isEmpty else { return }
        logger.info("[ShortNewsList] itemsScrolledPastTop | ids=\(ids, privacy: .public) count=\(ids.count)")
        itemsToMarkRead.send(ids)
    }

    // MARK: - Private

    private func bindReadTracking() {
        itemsToMarkRead
            .collect(.byTime(DispatchQueue.main, .milliseconds(300)))
            .map { batches in batches.flatMap { $0 } }
            .filter { !$0.isEmpty }
            .sink { [weak self] ids in
                guard let self else { return }
                // Deduplicate
                let uniqueIds = Array(Set(ids))
                logger.info("[ShortNewsList] Processing scroll-based mark read | ids=\(uniqueIds, privacy: .public) count=\(uniqueIds.count)")
                markBatchRead(ids: uniqueIds)
            }
            .store(in: &readCancellables)
    }

    private func bindReadStatusNotifications() {
        NotificationCenter.default.publisher(for: .contentMarkedAsRead)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] notification in
                guard let self,
                      let userInfo = notification.userInfo,
                      let contentId = userInfo["contentId"] as? Int,
                      let contentType = userInfo["contentType"] as? String
                else {
                    logger.warning("[ShortNewsList] Received contentMarkedAsRead with invalid userInfo")
                    return
                }

                logger.info("[ShortNewsList] Received contentMarkedAsRead notification | contentId=\(contentId) type=\(contentType, privacy: .public)")

                // Only update if it's news content
                guard contentType == "news" else {
                    logger.debug("[ShortNewsList] Ignoring non-news content | contentId=\(contentId) type=\(contentType, privacy: .public)")
                    return
                }

                // Update local state
                logger.info("[ShortNewsList] Updating local read state from notification | contentId=\(contentId)")
                markItemLocallyRead(id: contentId)
            }
            .store(in: &readCancellables)
    }

    private func markBatchRead(ids: [Int]) {
        logger.info("[ShortNewsList] markBatchRead called | ids=\(ids, privacy: .public)")

        // Filter to only unread items to avoid double-counting
        let unreadIds = ids.filter { id in
            currentItems().first { $0.id == id }?.isRead == false
        }

        guard !unreadIds.isEmpty else {
            logger.debug("[ShortNewsList] markBatchRead: all items already read, skipping")
            return
        }

        logger.info("[ShortNewsList] markBatchRead: marking \(unreadIds.count) unread items | ids=\(unreadIds, privacy: .public)")

        unreadIds.forEach { markItemLocallyRead(id: $0) }
        logger.debug("[ShortNewsList] Marked items locally read | count=\(unreadIds.count)")

        unreadCountService.decrementNewsCount(by: unreadIds.count)
        logger.debug("[ShortNewsList] Decremented unread count by \(unreadIds.count)")

        readRepository
            .markRead(ids: unreadIds)
            .receive(on: DispatchQueue.main)
            .sink { completion in
                if case .failure(let error) = completion {
                    logger.error("[ShortNewsList] markBatchRead API failed | ids=\(unreadIds, privacy: .public) error=\(error.localizedDescription)")
                }
            } receiveValue: { _ in
                logger.info("[ShortNewsList] markBatchRead API success | ids=\(unreadIds, privacy: .public)")
            }
            .store(in: &readCancellables)
    }
}
