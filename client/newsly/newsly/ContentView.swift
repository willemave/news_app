//
//  ContentView.swift
//  newsly
//
//  Created by Willem Ave on 7/8/25.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var unreadCountService = UnreadCountService.shared
    @StateObject private var readingStateStore = ReadingStateStore()
    @StateObject private var tabCoordinator: TabCoordinatorViewModel

    @State private var path = NavigationPath()
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

    var body: some View {
        NavigationStack(path: $path) {
            TabView(selection: $tabCoordinator.selectedTab) {
                LongFormView(
                    viewModel: tabCoordinator.longContentVM,
                    onSelect: { route in
                        path.append(route)
                    }
                )
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

                ChatSessionsView(onSelectSession: { route in
                    path.append(route)
                })
                    .tabItem {
                        Label("Chats", systemImage: "brain.head.profile")
                    }
                    .tag(RootTab.chats)

                FavoritesView()
                    .tabItem {
                        Label("Favorites", systemImage: "star.fill")
                    }
                    .tag(RootTab.favorites)

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
            tabCoordinator.handleTabChange(to: newValue)
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                restoreIfNeeded()
            }
        }
        .task {
            await unreadCountService.refreshCounts()
        }
    }

    private func restoreIfNeeded() {
        guard path.isEmpty, let state = readingStateStore.current else { return }

        tabCoordinator.selectedTab = state.contentType == .news ? .shortNews : .longContent
        let currentIds: [Int]
        if state.contentType == .news {
            let ids = tabCoordinator.shortNewsVM.currentItems().map(\.id)
            currentIds = ids.isEmpty ? [state.contentId] : ids
        } else {
            let ids = tabCoordinator.longContentVM.currentItems().map(\.id)
            currentIds = ids.isEmpty ? [state.contentId] : ids
        }

        path.append(
            ContentDetailRoute(
                contentId: state.contentId,
                contentType: state.contentType,
                allContentIds: currentIds
            )
        )
    }
}
