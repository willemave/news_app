//
//  NewsView.swift
//  newsly
//
//  Created by Assistant on 9/20/25.
//  Updated by Assistant on 10/12/25 for grouped display
//

import SwiftUI

struct NewsView: View {
    @StateObject private var viewModel = NewsGroupViewModel()

    var body: some View {
        NavigationStack {
            ZStack {
                VStack(spacing: 0) {
                    if viewModel.isLoading && viewModel.newsGroups.isEmpty {
                        LoadingView()
                    } else if let error = viewModel.errorMessage, viewModel.newsGroups.isEmpty {
                        ErrorView(message: error) {
                            Task { await viewModel.loadNewsGroups() }
                        }
                    } else if viewModel.newsGroups.isEmpty {
                        VStack(spacing: 16) {
                            Spacer()
                            Image(systemName: "newspaper")
                                .font(.largeTitle)
                                .foregroundColor(.secondary)
                            Text("No news items found.")
                                .foregroundColor(.secondary)
                            Spacer()
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else {
                        ScrollView {
                            LazyVStack(spacing: 16) {
                                ForEach(viewModel.newsGroups) { group in
                                    NewsGroupCard(
                                        group: group,
                                        onMarkAllAsRead: {
                                            await viewModel.markGroupAsRead(group.id)
                                        },
                                        onToggleFavorite: { itemId in
                                            await viewModel.toggleFavorite(itemId)
                                        },
                                        onConvert: { itemId in
                                            await viewModel.convertToArticle(itemId)
                                        }
                                    )
                                    .id(group.id)
                                    .onDisappear {
                                        // Mark as read when scrolled past
                                        Task {
                                            await viewModel.onGroupScrolledPast(group.id)
                                        }
                                    }
                                    .onAppear {
                                        // Load more when reaching near end
                                        if group.id == viewModel.newsGroups.last?.id {
                                            Task {
                                                await viewModel.loadMoreGroups()
                                            }
                                        }
                                    }
                                }

                                // Loading indicator at bottom
                                if viewModel.isLoadingMore {
                                    HStack {
                                        Spacer()
                                        ProgressView()
                                            .padding()
                                        Spacer()
                                    }
                                }
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                        }
                        .refreshable {
                            await viewModel.refresh()
                        }
                    }
                }
                .task {
                    await viewModel.loadNewsGroups()
                }
            }
            .navigationTitle("News")
        }
    }
}

#Preview {
    NewsView()
}
