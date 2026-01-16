//
//  MoreView.swift
//  newsly
//

import SwiftUI

struct MoreView: View {
    @ObservedObject var submissionsViewModel: SubmissionStatusViewModel
    @StateObject private var processingCountService = ProcessingCountService.shared

    var body: some View {
        List {
            Section {
                menuRow(
                    destination: SearchView(),
                    icon: "magnifyingglass",
                    title: "Search"
                )

                menuRow(
                    destination: FavoritesView(),
                    icon: "star",
                    title: "Favorites"
                )

                menuRow(
                    destination: RecentlyReadView(),
                    icon: "clock",
                    title: "Recently Read"
                )

                NavigationLink {
                    SubmissionsView(viewModel: submissionsViewModel)
                } label: {
                    HStack(spacing: 16) {
                        minimalIcon("tray.and.arrow.up")
                        Text("Submissions")
                            .foregroundStyle(.primary)
                        Spacer()
                        if submissionsViewModel.submissions.count > 0 {
                            minimalBadge(count: submissionsViewModel.submissions.count, color: .red)
                        }
                    }
                    .frame(minHeight: 44)
                }

                NavigationLink {
                    ProcessingStatsView()
                } label: {
                    HStack(spacing: 16) {
                        minimalIcon("clock.arrow.circlepath")
                        Text("Processing")
                            .foregroundStyle(.primary)
                        Spacer()
                        if processingCountService.processingCount > 0 {
                            minimalBadge(count: processingCountService.processingCount, color: .teal)
                        }
                    }
                    .frame(minHeight: 44)
                }
            }

            Section {
                menuRow(
                    destination: SettingsView(),
                    icon: "gearshape",
                    title: "Settings"
                )
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("More")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await submissionsViewModel.load()
            await processingCountService.refreshCount()
        }
    }

    private func menuRow<D: View>(destination: D, icon: String, title: String) -> some View {
        NavigationLink {
            destination
        } label: {
            HStack(spacing: 16) {
                minimalIcon(icon)
                Text(title)
                    .foregroundStyle(.primary)
            }
            .frame(minHeight: 44)
        }
    }

    private func minimalIcon(_ name: String) -> some View {
        Image(systemName: name)
            .font(.system(size: 20, weight: .regular))
            .foregroundStyle(.secondary)
            .frame(width: 24, height: 24)
    }

    private func minimalBadge(count: Int, color: Color) -> some View {
        Text("\(count)")
            .font(.system(size: 14, weight: .medium))
            .foregroundStyle(color)
            .monospacedDigit()
    }
}

#Preview {
    MoreView(submissionsViewModel: SubmissionStatusViewModel())
}
