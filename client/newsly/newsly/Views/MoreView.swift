//
//  MoreView.swift
//  newsly
//

import SwiftUI

struct MoreView: View {
    var body: some View {
        List {
            NavigationLink {
                SearchView()
            } label: {
                Label("Search", systemImage: "magnifyingglass")
            }

            NavigationLink {
                RecentlyReadView()
            } label: {
                Label("Recently Read", systemImage: "clock.fill")
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

#Preview {
    MoreView()
}
