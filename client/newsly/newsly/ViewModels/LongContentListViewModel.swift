//
//  LongContentListViewModel.swift
//  newsly
//
//  Created by Assistant on 3/16/26.
//

import Combine
import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "LongContentList")

@MainActor
final class LongContentListViewModel: BaseContentListViewModel {
    private let readRepository: ReadStatusRepositoryType
    private let unreadCountService: UnreadCountService
    private let contentService: ContentService

    private var cancellables = Set<AnyCancellable>()

    init(
        repository: ContentRepositoryType,
        readRepository: ReadStatusRepositoryType,
        unreadCountService: UnreadCountService,
        contentService: ContentService = .shared
    ) {
        self.readRepository = readRepository
        self.unreadCountService = unreadCountService
        self.contentService = contentService
        super.init(
            repository: repository,
            contentTypes: [.article, .podcast],
            readFilter: .unread
        )
        bindReadStatusNotifications()
        logger.info("[LongContentList] ViewModel initialized")
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
                    logger.warning("[LongContentList] Received contentMarkedAsRead with invalid userInfo")
                    return
                }

                logger.info("[LongContentList] Received contentMarkedAsRead notification | contentId=\(contentId) type=\(contentType, privacy: .public)")

                // Only update if it's article or podcast content
                guard contentType == "article" || contentType == "podcast" else {
                    logger.debug("[LongContentList] Ignoring non-article/podcast content | contentId=\(contentId) type=\(contentType, privacy: .public)")
                    return
                }

                // Update local state
                logger.info("[LongContentList] Updating local read state | contentId=\(contentId)")
                markItemLocallyRead(id: contentId)
            }
            .store(in: &cancellables)
    }

    func refresh() {
        logger.info("[LongContentList] refresh called")
        startInitialLoad()
    }

    func setReadFilter(_ filter: ReadFilter) {
        logger.info("[LongContentList] setReadFilter | filter=\(String(describing: filter), privacy: .public)")
        updateReadFilter(filter)
    }

    func markAsRead(_ id: Int) {
        logger.info("[LongContentList] markAsRead called | id=\(id)")

        guard let item = currentItems().first(where: { $0.id == id }) else {
            logger.warning("[LongContentList] markAsRead failed: item not found | id=\(id)")
            return
        }

        markItemLocallyRead(id: id)
        decrementCount(for: item)
        logger.debug("[LongContentList] Marked locally read | id=\(id) type=\(item.contentType, privacy: .public)")

        readRepository
            .markRead(ids: [id])
            .receive(on: DispatchQueue.main)
            .sink { completion in
                if case .failure(let error) = completion {
                    logger.error("[LongContentList] markAsRead API failed | id=\(id) error=\(error.localizedDescription)")
                }
            } receiveValue: { _ in
                logger.info("[LongContentList] markAsRead API success | id=\(id)")
            }
            .store(in: &cancellables)
    }

    func markAllVisibleAsRead() async {
        let unreadItems = currentItems().filter { !$0.isRead }
        guard !unreadItems.isEmpty else {
            logger.debug("[LongContentList] markAllVisibleAsRead: no unread items")
            return
        }

        let ids = unreadItems.map(\.id)
        logger.info("[LongContentList] markAllVisibleAsRead | ids=\(ids, privacy: .public) count=\(ids.count)")

        let reductions = unreadItems.reduce(into: (articles: 0, podcasts: 0)) { partial, item in
            switch item.contentTypeEnum {
            case .article:
                partial.articles += 1
            case .podcast:
                partial.podcasts += 1
            default:
                break
            }
        }

        unreadItems.forEach { markItemLocallyRead(id: $0.id) }

        if reductions.articles > 0 {
            unreadCountService.decrementArticleCount(by: reductions.articles)
        }
        if reductions.podcasts > 0 {
            unreadCountService.decrementPodcastCount(by: reductions.podcasts)
        }
        logger.debug("[LongContentList] Decremented counts | articles=\(reductions.articles) podcasts=\(reductions.podcasts)")

        await withCheckedContinuation { continuation in
            readRepository
                .markRead(ids: ids)
                .receive(on: DispatchQueue.main)
                .sink { completion in
                    if case .failure(let error) = completion {
                        logger.error("[LongContentList] markAllVisibleAsRead API failed | error=\(error.localizedDescription)")
                    }
                    continuation.resume()
                } receiveValue: { _ in
                    logger.info("[LongContentList] markAllVisibleAsRead API success | count=\(ids.count)")
                }
                .store(in: &cancellables)
        }
    }

    func toggleFavorite(_ contentId: Int) async {
        logger.info("[LongContentList] toggleFavorite called | contentId=\(contentId)")

        guard let current = currentItems().first(where: { $0.id == contentId }) else {
            logger.warning("[LongContentList] toggleFavorite failed: item not found | contentId=\(contentId)")
            return
        }
        updateItem(id: contentId) { $0.updating(isFavorited: !current.isFavorited) }

        do {
            let response = try await contentService.toggleFavorite(id: contentId)
            if let isFavorited = response["is_favorited"] as? Bool {
                updateItem(id: contentId) { $0.updating(isFavorited: isFavorited) }
                logger.info("[LongContentList] toggleFavorite success | contentId=\(contentId) isFavorited=\(isFavorited)")
            }
        } catch {
            updateItem(id: contentId) { $0.updating(isFavorited: current.isFavorited) }
            logger.error("[LongContentList] toggleFavorite failed | contentId=\(contentId) error=\(error.localizedDescription)")
        }
    }

    private func decrementCount(for item: ContentSummary) {
        switch item.contentTypeEnum {
        case .article:
            unreadCountService.decrementArticleCount()
        case .podcast:
            unreadCountService.decrementPodcastCount()
        default:
            break
        }
    }
}
