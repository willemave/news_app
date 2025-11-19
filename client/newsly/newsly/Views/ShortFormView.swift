//
//  ShortFormView.swift
//  newsly
//
//  Created by Assistant on 11/4/25.
//

import SwiftUI

struct ShortFormView: View {
    @StateObject private var viewModel = NewsGroupViewModel()
    @State private var lastMetrics: (h: CGFloat, w: CGFloat)?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if viewModel.isLoading && viewModel.newsGroups.isEmpty {
                    LoadingView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = viewModel.errorMessage, viewModel.newsGroups.isEmpty {
                    ErrorView(message: error) {
                        Task { await viewModel.loadNewsGroups() }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if viewModel.newsGroups.isEmpty {
                    VStack(spacing: 16) {
                        Spacer()
                        Image(systemName: "bolt.fill")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        Text("No short-form content found.")
                            .foregroundColor(.secondary)
                        Spacer()
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    PagedCardView(
                        groups: viewModel.newsGroups,
                        onMarkRead: { groupId in
                            await viewModel.markGroupAsRead(groupId)
                        },
                        onConvert: { itemId in
                            await viewModel.convertToArticle(itemId)
                        },
                        onNearEnd: {
                            await viewModel.preloadNextGroups()
                        },
                        onCardHeightMeasured: { cardHeight, textWidth in
                            handleCardHeightMeasured(cardHeight: cardHeight, textWidth: textWidth)
                        }
                    )
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .refreshable {
                        await viewModel.refresh()
                    }
                }
            }
            .task {
                // Initial load - metrics will be set by PagedCardView callback
                await viewModel.loadNewsGroups(preserveReadGroups: false)
            }
            .onDisappear {
                viewModel.clearSessionReads()
            }
        }
    }

    /// Handle cardHeight measurement from PagedCardView
    /// This provides the single source of truth for grouping logic
    private func handleCardHeightMeasured(cardHeight: CGFloat, textWidth: CGFloat) {
        guard cardHeight > 200 else { return }

        // Set grouping metrics using the exact cardHeight that PagedCardView will use
        viewModel.setGroupingMetrics(contentWidth: textWidth, availableHeight: cardHeight)

        // Calculate optimal group size based on cardHeight (kept for paging limits and prefetch sizing)
        let newGroupSize = [ContentSummary].calculateOptimalGroupSize(availableHeight: cardHeight)
        if newGroupSize != viewModel.groupSize {
            viewModel.groupSize = newGroupSize
        }

        // Reload when metrics changed (first time or by > 1 pt)
        let metricsChanged =
            lastMetrics == nil
            || abs(lastMetrics!.h - cardHeight) > 1
            || abs(lastMetrics!.w - textWidth) > 1

        if metricsChanged {
            print("✅ CardHeight measured: \(cardHeight), textWidth: \(textWidth)")
            print("✅ Group size: \(viewModel.groupSize), reloading with height-aware packer")
            Task {
                await viewModel.loadNewsGroups(preserveReadGroups: true)
            }
            lastMetrics = (cardHeight, textWidth)
        }
    }
}

#Preview {
    ShortFormView()
}
