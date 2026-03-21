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
    @StateObject private var submissionStatusViewModel = SubmissionStatusViewModel()
    @ObservedObject private var settings = AppSettings.shared

    @State private var longFormPath = NavigationPath()
    @State private var shortFormPath = NavigationPath()
    @State private var knowledgePath = NavigationPath()
    @State private var knowledgePrefersHistory = false
    @State private var isRestoringPath = false
    @Environment(\.scenePhase) private var scenePhase

    init() {
        // Style the system tab bar with terracotta theme
        let terracotta = UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? UIColor(red: 0.831, green: 0.514, blue: 0.416, alpha: 1.0)
                : UIColor(red: 0.439, green: 0.169, blue: 0.098, alpha: 1.0)
        }
        let unselected = UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? UIColor(red: 0.639, green: 0.616, blue: 0.588, alpha: 1.0)
                : UIColor(red: 0.396, green: 0.365, blue: 0.337, alpha: 1.0)
        }
        let surface = UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? UIColor(red: 0.102, green: 0.094, blue: 0.082, alpha: 1.0)
                : UIColor(red: 0.992, green: 0.976, blue: 0.957, alpha: 1.0)
        }

        let itemAppearance = UITabBarItemAppearance()
        itemAppearance.selected.iconColor = terracotta
        itemAppearance.selected.titleTextAttributes = [.foregroundColor: terracotta]
        itemAppearance.normal.iconColor = unselected
        itemAppearance.normal.titleTextAttributes = [.foregroundColor: unselected]

        let appearance = UITabBarAppearance()
        appearance.configureWithDefaultBackground()
        appearance.backgroundColor = surface.withAlphaComponent(0.9)
        appearance.stackedLayoutAppearance = itemAppearance
        appearance.inlineLayoutAppearance = itemAppearance
        appearance.compactInlineLayoutAppearance = itemAppearance
        UITabBar.appearance().standardAppearance = appearance
        UITabBar.appearance().scrollEdgeAppearance = appearance

        // Style navigation bar with warm tones
        let navAppearance = UINavigationBarAppearance()
        navAppearance.configureWithDefaultBackground()
        navAppearance.backgroundColor = surface.withAlphaComponent(0.9)
        UINavigationBar.appearance().standardAppearance = navAppearance
        UINavigationBar.appearance().scrollEdgeAppearance = navAppearance
        UINavigationBar.appearance().tintColor = terracotta

        let contentRepository = ContentRepository()
        let readRepository = ReadStatusRepository()
        let unreadService = UnreadCountService.shared

        let shortNewsVM = ShortNewsListViewModel(
            repository: contentRepository,
            readRepository: readRepository,
            unreadCountService: unreadService
        )
        let dailyDigestVM = DailyDigestListViewModel(
            repository: DailyNewsDigestRepository(),
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
                dailyDigestVM: dailyDigestVM,
                longContentVM: longContentVM
            )
        )
    }

    private var contentTextSize: DynamicTypeSize {
        ContentTextSize(index: settings.contentTextSizeIndex).dynamicTypeSize
    }

    private var longBadge: String? {
        let total = unreadCountService.articleCount + unreadCountService.podcastCount
        return total > 0 ? String(total) : nil
    }

    private var shortBadge: String? {
        let mode = FastNewsMode(rawValue: settings.fastNewsMode) ?? .dailyDigest
        let count = mode == .dailyDigest
            ? unreadCountService.dailyNewsDigestCount
            : unreadCountService.newsCount
        return count > 0 ? String(count) : nil
    }

    private var knowledgeBadge: String? {
        // Show processing indicator if any sessions are being processed
        chatSessionManager.hasProcessingSessions ? "●" : nil
    }

    private var moreBadge: String? {
        let count = submissionStatusViewModel.submissions.count
        return count > 0 ? String(count) : nil
    }

    var body: some View {
        TabView(selection: $tabCoordinator.selectedTab) {
            NavigationStack(path: $longFormPath) {
                LongFormView(
                    viewModel: tabCoordinator.longContentVM,
                    onSelect: { route in
                        longFormPath.append(route)
                    }
                )
                .withContentRoutes(
                    tab: .longContent,
                    path: $longFormPath,
                    readingStateStore: readingStateStore,
                    contentTextSize: contentTextSize
                )
            }
            .tag(RootTab.longContent)
            .tabItem {
                Label("Long Form", systemImage: "doc.richtext")
            }
            .badge(longBadge != nil ? Int(longBadge!) ?? 0 : 0)

            NavigationStack(path: $shortFormPath) {
                if (FastNewsMode(rawValue: settings.fastNewsMode) ?? .dailyDigest) == .dailyDigest {
                    DailyDigestShortFormView(
                        viewModel: tabCoordinator.dailyDigestVM,
                        onOpenChatSession: { route in
                            shortFormPath.append(route)
                        }
                    )
                    .withContentRoutes(
                        tab: .shortNews,
                        path: $shortFormPath,
                        readingStateStore: readingStateStore,
                        contentTextSize: contentTextSize
                    )
                } else {
                    ShortFormView(
                        viewModel: tabCoordinator.shortNewsVM,
                        onSelect: { route in
                            shortFormPath.append(route)
                        }
                    )
                    .withContentRoutes(
                        tab: .shortNews,
                        path: $shortFormPath,
                        readingStateStore: readingStateStore,
                        contentTextSize: contentTextSize
                    )
                }
            }
            .tag(RootTab.shortNews)
            .tabItem {
                Label("Fast News", systemImage: "bolt.fill")
            }
            .badge(shortBadge != nil ? Int(shortBadge!) ?? 0 : 0)

            NavigationStack(path: $knowledgePath) {
                KnowledgeView(
                    prefersHistoryView: $knowledgePrefersHistory,
                    onSelectSession: { route in
                        knowledgePath.append(route)
                    },
                    onSelectContent: { route in
                        knowledgePath.append(route)
                    }
                )
                .withContentRoutes(
                    tab: .knowledge,
                    path: $knowledgePath,
                    onShowKnowledgeHistory: {
                        knowledgePrefersHistory = true
                    },
                    readingStateStore: readingStateStore,
                    contentTextSize: contentTextSize
                )
            }
            .tag(RootTab.knowledge)
            .tabItem {
                Label("Knowledge", systemImage: "books.vertical.fill")
            }

            NavigationStack {
                MoreView(submissionsViewModel: submissionStatusViewModel)
            }
            .tag(RootTab.more)
            .tabItem {
                Label("More", systemImage: "ellipsis.circle.fill")
            }
            .badge(moreBadge != nil ? Int(moreBadge!) ?? 0 : 0)
        }
        .tint(Color.terracottaPrimary)
        .dynamicTypeSize(AppTextSize(index: settings.appTextSizeIndex).dynamicTypeSize)
        .environmentObject(readingStateStore)
        .onAppear {
            tabCoordinator.ensureInitialLoads()
            restoreIfNeeded()
        }
        .onChange(of: tabCoordinator.selectedTab) { _, newValue in
            logger.info("[TabChange] selectedTab=\(String(describing: newValue), privacy: .public)")
            if newValue == .knowledge {
                knowledgePrefersHistory = false
            }
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
            await submissionStatusViewModel.load()
        }
    }

    private func restoreIfNeeded() {
        let isNews = readingStateStore.current?.contentType == .news
        let isDailyDigestMode = (FastNewsMode(rawValue: settings.fastNewsMode) ?? .dailyDigest) == .dailyDigest
        if isNews && isDailyDigestMode {
            return
        }
        let targetPath = isNews ? shortFormPath : longFormPath
        guard !isRestoringPath, targetPath.isEmpty, let state = readingStateStore.current else { return }

        isRestoringPath = true
        logger.info(
            "[NavigationRestore] contentId=\(state.contentId, privacy: .public) contentType=\(state.contentType.rawValue, privacy: .public)"
        )
        let targetTab: RootTab = isNews ? .shortNews : .longContent
        if tabCoordinator.selectedTab != targetTab {
            tabCoordinator.selectedTab = targetTab
        }

        Task { @MainActor in
            await Task.yield()
            defer { isRestoringPath = false }

            let currentIds: [Int]
            if isNews {
                guard shortFormPath.isEmpty else { return }
                let ids = tabCoordinator.shortNewsVM.currentItems().map(\.id)
                currentIds = ids.isEmpty ? [state.contentId] : ids
            } else {
                guard longFormPath.isEmpty else { return }
                let ids = tabCoordinator.longContentVM.currentItems().map(\.id)
                currentIds = ids.isEmpty ? [state.contentId] : ids
            }

            let route = ContentDetailRoute(
                contentId: state.contentId,
                contentType: state.contentType,
                allContentIds: currentIds
            )

            var transaction = Transaction()
            transaction.disablesAnimations = true
            withTransaction(transaction) {
                if isNews {
                    shortFormPath.append(route)
                } else {
                    longFormPath.append(route)
                }
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
        openChatSession(sessionId: sessionId)
    }

    private func openChatSession(sessionId: Int) {
        tabCoordinator.selectedTab = .knowledge
        knowledgePrefersHistory = false
        knowledgePath = NavigationPath()
        knowledgePath.append(ChatSessionRoute(sessionId: sessionId))
    }
}

// MARK: - Content navigation destinations

private extension View {
    func withContentRoutes(
        tab: RootTab,
        path: Binding<NavigationPath>,
        onShowKnowledgeHistory: (() -> Void)? = nil,
        readingStateStore: ReadingStateStore,
        contentTextSize: DynamicTypeSize
    ) -> some View {
        self
            .navigationDestination(for: ContentDetailRoute.self) { route in
                ContentDetailView(
                    contentId: route.contentId,
                    allContentIds: route.allContentIds
                )
                .dynamicTypeSize(contentTextSize)
                .environmentObject(readingStateStore)
            }
            .navigationDestination(for: ChatSessionRoute.self) { route in
                ChatSessionView(
                    sessionId: route.sessionId,
                    onShowHistory: tab == .knowledge
                        ? {
                            onShowKnowledgeHistory?()
                            path.wrappedValue = NavigationPath()
                        }
                        : nil
                )
            }
    }
}
