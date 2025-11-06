//
//  ShortFormView.swift
//  newsly
//
//  Created by Assistant on 11/4/25.
//

import SwiftUI

struct ShortFormView: View {
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
        }
    }
}

#Preview {
    ShortFormView()
}
