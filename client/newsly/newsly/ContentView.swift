//
//  ContentView.swift
//  newsly
//
//  Created by Willem Ave on 7/8/25.
//

import os.log
import SwiftUI

private let logger = Logger(subsystem: "com.newsly", category: "ContentView")

struct ContentView: View {
    @StateObject private var unreadCountService = UnreadCountService.shared
    @StateObject private var readingStateStore = ReadingStateStore()
    @StateObject private var tabCoordinator: TabCoordinatorViewModel
    @StateObject private var chatSessionManager = ActiveChatSessionManager.shared
    @ObservedObject private var settings = AppSettings.shared

    @State private var path = NavigationPath()
    @State private var isRestoringPath = false
    @Environment(\.scenePhase) private var scenePhase

    init() {
        let contentRepository = ContentRepository()
        let readRepository = ReadStatusRepository()
        let unreadService = UnreadCountService.shared

        let shortNewsVM = ShortNewsListViewModel(
            repository: contentRepository,
            readRepository: readRepository,
            unreadCountService: unreadService
        )
        let longContentVM = LongContentListViewModel(
            repository: contentRepository,
            readRepository: readRepository,
            unreadCountService: unreadService
        )

        _tabCoordinator = StateObject(
            wrappedValue: TabCoordinatorViewModel(
                shortNewsVM: shortNewsVM,
                longContentVM: longContentVM
            )
        )
    }

    private var longBadge: String? {
        let total = unreadCountService.articleCount + unreadCountService.podcastCount
        return total > 0 ? String(total) : nil
    }

    private var shortBadge: String? {
        unreadCountService.newsCount > 0 ? String(unreadCountService.newsCount) : nil
    }

    private var knowledgeBadge: String? {
        // Show processing indicator if any sessions are being processed
        chatSessionManager.hasProcessingSessions ? "●" : nil
    }

    var body: some View {
        NavigationStack(path: $path) {
            TabView(selection: $tabCoordinator.selectedTab) {
                Group {
                    if settings.useLongFormCardStack {
                        LongFormCardStackView(
                            viewModel: tabCoordinator.longContentVM,
                            onSelect: { route in
                                path.append(route)
                            }
                        )
                    } else {
                        LongFormView(
                            viewModel: tabCoordinator.longContentVM,
                            onSelect: { route in
                                path.append(route)
                            }
                        )
                    }
                }
                .tabItem {
                    Label("Long", systemImage: "doc.richtext")
                }
                .badge(longBadge)
                .tag(RootTab.longContent)

                ShortFormView(
                    viewModel: tabCoordinator.shortNewsVM,
                    onSelect: { route in
                        path.append(route)
                    }
                )
                .tabItem {
                    Label("Short", systemImage: "bolt.fill")
                }
                .badge(shortBadge)
                .tag(RootTab.shortNews)

                KnowledgeView(
                    onSelectSession: { route in
                        path.append(route)
                    },
                    onSelectContent: { route in
                        path.append(route)
                    }
                )
                    .tabItem {
                        Label("Knowledge", systemImage: "books.vertical.fill")
                    }
                    .badge(knowledgeBadge)
                    .tag(RootTab.knowledge)

                MoreView()
                    .tabItem {
                        Label("More", systemImage: "ellipsis.circle.fill")
                    }
                    .tag(RootTab.more)
            }
            .navigationDestination(for: ContentDetailRoute.self) { route in
                ContentDetailView(
                    contentId: route.contentId,
                    allContentIds: route.allContentIds
                )
                .environmentObject(readingStateStore)
            }
            .navigationDestination(for: ChatSessionRoute.self) { route in
                ChatSessionView(sessionId: route.sessionId)
            }
        }
        .environmentObject(readingStateStore)
        .onAppear {
            tabCoordinator.ensureInitialLoads()
            restoreIfNeeded()
        }
    .onChange(of: tabCoordinator.selectedTab) { _, newValue in
        logger.info("[TabChange] selectedTab=\(String(describing: newValue), privacy: .public)")
        tabCoordinator.handleTabChange(to: newValue)
    }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                restoreIfNeeded()
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .openChatSession)) { notification in
            handleOpenChatSession(notification)
        }
        .task {
            await unreadCountService.refreshCounts()
        }
    }

    private func restoreIfNeeded() {
        guard !isRestoringPath, path.isEmpty, let state = readingStateStore.current else { return }

        isRestoringPath = true
        logger.info(
            "[NavigationRestore] contentId=\(state.contentId, privacy: .public) contentType=\(state.contentType.rawValue, privacy: .public)"
        )
        let targetTab: RootTab = state.contentType == .news ? .shortNews : .longContent
        if tabCoordinator.selectedTab != targetTab {
            tabCoordinator.selectedTab = targetTab
        }

        Task { @MainActor in
            await Task.yield()
            defer { isRestoringPath = false }
            guard path.isEmpty else { return }

            let currentIds: [Int]
            if state.contentType == .news {
                let ids = tabCoordinator.shortNewsVM.currentItems().map(\.id)
                currentIds = ids.isEmpty ? [state.contentId] : ids
            } else {
                let ids = tabCoordinator.longContentVM.currentItems().map(\.id)
                currentIds = ids.isEmpty ? [state.contentId] : ids
            }

            var transaction = Transaction()
            transaction.disablesAnimations = true
            withTransaction(transaction) {
                path.append(
                    ContentDetailRoute(
                        contentId: state.contentId,
                        contentType: state.contentType,
                        allContentIds: currentIds
                    )
                )
            }
            logger.info("[NavigationRestore] pathRestored idsCount=\(currentIds.count, privacy: .public)")
        }
    }

    private func handleOpenChatSession(_ notification: Notification) {
        let sessionId: Int?
        if let id = notification.userInfo?["session_id"] as? Int {
            sessionId = id
        } else if let id = notification.userInfo?["session_id"] as? NSNumber {
            sessionId = id.intValue
        } else {
            sessionId = nil
        }

        guard let sessionId else {
            logger.error("[Notification] openChatSession missing session_id")
            return
        }

        logger.info("[Notification] openChatSession sessionId=\(sessionId, privacy: .public)")
        path.append(ChatSessionRoute(sessionId: sessionId))
    }
}
