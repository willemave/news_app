//
//  NewsView.swift
//  newsly
//
//  Created by Assistant on 9/20/25.
//  Updated by Assistant on 10/12/25 for grouped display
//  Updated by Assistant on 11/01/25 for button navigation
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
                        PagedCardView(
                            groups: viewModel.newsGroups,
                            onDismiss: { groupId in
                                await viewModel.markGroupAsRead(groupId)
                                await viewModel.preloadNextGroups()
                            },
                            onConvert: { itemId in
                                await viewModel.convertToArticle(itemId)
                            }
                        )
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
