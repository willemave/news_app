//
//  ContentView.swift
//  newsly
//
//  Created by Willem Ave on 7/8/25.
//

import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            ArticlesView()
                .tabItem {
                    Label("Articles", systemImage: "doc.text")
                }
            
            PodcastsView()
                .tabItem {
                    Label("Podcasts", systemImage: "mic")
                }
            
            FavoritesView()
                .tabItem {
                    Label("Favorites", systemImage: "star.fill")
                }
            
            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
        }
    }
}

#Preview {
    ContentView()
}
