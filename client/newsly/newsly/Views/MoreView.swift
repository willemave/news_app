//
//  MoreView.swift
//  newsly
//

import SwiftUI

struct MoreView: View {
    @ObservedObject var submissionsViewModel: SubmissionStatusViewModel

    var body: some View {
        List {
            NavigationLink {
                SearchView()
            } label: {
                Label("Search", systemImage: "magnifyingglass")
            }

            NavigationLink {
                FavoritesView()
            } label: {
                Label("Favorites", systemImage: "star")
            }

            NavigationLink {
                RecentlyReadView()
            } label: {
                Label("Recently Read", systemImage: "clock.fill")
            }

            NavigationLink {
                SubmissionsView(viewModel: submissionsViewModel)
            } label: {
                HStack {
                    Label("Submissions", systemImage: "tray.and.arrow.up")
                    Spacer()
                    if submissionsViewModel.submissions.count > 0 {
                        submissionsBadge(count: submissionsViewModel.submissions.count)
                    }
                }
            }

            NavigationLink {
                SettingsView()
            } label: {
                Label("Settings", systemImage: "gear")
            }
        }
        .navigationTitle("More")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await submissionsViewModel.load()
        }
    }

    private func submissionsBadge(count: Int) -> some View {
        Text("\(count)")
            .font(.caption2)
            .fontWeight(.semibold)
            .foregroundStyle(Color.white)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Color.red)
            .clipShape(Capsule())
    }
}

#Preview {
    MoreView(submissionsViewModel: SubmissionStatusViewModel())
}
