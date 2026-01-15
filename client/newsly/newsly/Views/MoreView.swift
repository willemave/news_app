//
//  MoreView.swift
//  newsly
//

import SwiftUI

struct MoreView: View {
    @ObservedObject var submissionsViewModel: SubmissionStatusViewModel

    var body: some View {
        List {
            Section {
                menuRow(
                    destination: SearchView(),
                    icon: "magnifyingglass",
                    iconColor: .blue,
                    title: "Search"
                )

                menuRow(
                    destination: FavoritesView(),
                    icon: "star.fill",
                    iconColor: .yellow,
                    title: "Favorites"
                )

                menuRow(
                    destination: RecentlyReadView(),
                    icon: "clock.fill",
                    iconColor: .orange,
                    title: "Recently Read"
                )

                NavigationLink {
                    SubmissionsView(viewModel: submissionsViewModel)
                } label: {
                    HStack(spacing: 12) {
                        iconView(icon: "tray.and.arrow.up.fill", color: .purple)
                        Text("Submissions")
                        Spacer()
                        if submissionsViewModel.submissions.count > 0 {
                            submissionsBadge(count: submissionsViewModel.submissions.count)
                        }
                    }
                }
            }

            Section {
                menuRow(
                    destination: SettingsView(),
                    icon: "gear",
                    iconColor: .gray,
                    title: "Settings"
                )
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("More")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await submissionsViewModel.load()
        }
    }

    private func menuRow<D: View>(destination: D, icon: String, iconColor: Color, title: String) -> some View {
        NavigationLink {
            destination
        } label: {
            HStack(spacing: 12) {
                iconView(icon: icon, color: iconColor)
                Text(title)
            }
        }
    }

    private func iconView(icon: String, color: Color) -> some View {
        Image(systemName: icon)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: 28, height: 28)
            .background(color.gradient)
            .clipShape(RoundedRectangle(cornerRadius: 6))
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
