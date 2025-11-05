//
//  ContentView.swift
//  newsly
//
//  Created by Willem Ave on 7/8/25.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var unreadCountService = UnreadCountService.shared

    private var longBadge: String? {
        let total = unreadCountService.articleCount + unreadCountService.podcastCount
        return total > 0 ? String(total) : nil
    }
    private var shortBadge: String? {
        unreadCountService.newsCount > 0 ? String(unreadCountService.newsCount) : nil
    }

    var body: some View {
        TabView {
            LongFormView()
                .tabItem {
                    Label("Long", systemImage: "doc.richtext")
                }
                .badge(longBadge)

            ShortFormView()
                .tabItem {
                    Label("Short", systemImage: "bolt.fill")
                }
                .badge(shortBadge)

            SearchView()
                .tabItem {
                    Label("Search", systemImage: "magnifyingglass")
                }

            FavoritesView()
                .tabItem {
                    Label("Favorites", systemImage: "star.fill")
                }

            RecentlyReadView()
                .tabItem {
                    Label("Recently Read", systemImage: "clock.fill")
                }

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
        }
        .task {
            await unreadCountService.refreshCounts()
        }
    }
}

#Preview {
    ContentView()
}
