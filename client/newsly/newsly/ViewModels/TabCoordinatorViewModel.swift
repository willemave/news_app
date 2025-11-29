//
//  TabCoordinatorViewModel.swift
//  newsly
//
//  Created by Assistant on 3/16/26.
//

import Foundation

enum RootTab: Hashable {
    case longContent
    case shortNews
    case chats
    case favorites
    case more
}

@MainActor
final class TabCoordinatorViewModel: ObservableObject {
    @Published var selectedTab: RootTab

    let shortNewsVM: ShortNewsListViewModel
    let longContentVM: LongContentListViewModel

    private var previousTab: RootTab

    init(
        shortNewsVM: ShortNewsListViewModel,
        longContentVM: LongContentListViewModel,
        initialTab: RootTab = .shortNews
    ) {
        self.shortNewsVM = shortNewsVM
        self.longContentVM = longContentVM
        self.selectedTab = initialTab
        self.previousTab = initialTab
    }

    func handleTabChange(to newTab: RootTab) {
        guard newTab != previousTab else { return }

        switch previousTab {
        case .shortNews:
            shortNewsVM.clearReadTrigger.send(())
            shortNewsVM.startInitialLoad()
        case .longContent:
            longContentVM.clearReadTrigger.send(())
            longContentVM.startInitialLoad()
        case .chats, .favorites, .more:
            break
        }

        previousTab = newTab
        ensureTabLoaded(newTab)
    }

    func ensureInitialLoads() {
        ensureTabLoaded(selectedTab)
    }

    private func ensureTabLoaded(_ tab: RootTab) {
        switch tab {
        case .shortNews:
            if shortNewsVM.currentItems().isEmpty {
                shortNewsVM.refreshTrigger.send(())
            }
        case .longContent:
            if longContentVM.currentItems().isEmpty {
                longContentVM.refreshTrigger.send(())
            }
        case .chats, .favorites, .more:
            break
        }
    }
}
