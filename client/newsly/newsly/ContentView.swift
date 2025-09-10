//
//  ContentView.swift
//  newsly
//
//  Created by Willem Ave on 7/8/25.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var unreadCountService = UnreadCountService.shared
    
    private var articleBadge: String? { unreadCountService.articleCount > 0 ? String(unreadCountService.articleCount) : nil }
    private var podcastBadge: String? { unreadCountService.podcastCount > 0 ? String(unreadCountService.podcastCount) : nil }
    
    var body: some View {
        TabView {
            ArticlesView()
                .tabItem {
                    Label("Articles", systemImage: "doc.text")
                }
                .badge(articleBadge)
            
            PodcastsView()
                .tabItem {
                    Label("Podcasts", systemImage: "mic")
                }
                .badge(podcastBadge)
            
            FavoritesView()
                .tabItem {
                    Label("Favorites", systemImage: "star.fill")
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
