//
//  MoreView.swift
//  newsly
//

import SwiftUI

struct MoreView: View {
    var body: some View {
        NavigationView {
            List {
                NavigationLink {
                    SearchView()
                } label: {
                    Label("Search", systemImage: "magnifyingglass")
                }

                NavigationLink {
                    FavoritesView()
                } label: {
                    Label("Favorites", systemImage: "star.fill")
                }

                NavigationLink {
                    SettingsView()
                } label: {
                    Label("Settings", systemImage: "gear")
                }
            }
            .navigationTitle("More")
            .navigationBarTitleDisplayMode(.large)
        }
    }
}

#Preview {
    MoreView()
}
