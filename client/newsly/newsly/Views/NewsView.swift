//
//  NewsView.swift
//  newsly
//
//  Created by Assistant on 9/20/25.
//

import SwiftUI

struct NewsView: View {
    @StateObject private var viewModel = ContentListViewModel()
    @ObservedObject private var settings = AppSettings.shared

    var body: some View {
        NavigationStack {
            ZStack {
                VStack(spacing: 0) {
                    if viewModel.isLoading && viewModel.contents.isEmpty {
                        LoadingView()
                    } else if let error = viewModel.errorMessage, viewModel.contents.isEmpty {
                        ErrorView(message: error) {
                            Task { await viewModel.loadContent() }
                        }
                    } else if viewModel.contents.isEmpty {
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
                        List {
                            ForEach(viewModel.contents) { content in
                                ZStack {
                                    NavigationLink(destination: ContentDetailView(
                                        contentId: content.id,
                                        allContentIds: viewModel.contents.map { $0.id }
                                    )) { EmptyView() }
                                        .opacity(0)
                                        .buttonStyle(PlainButtonStyle())

                                    ContentCard(
                                        content: content,
                                        onMarkAsRead: { await viewModel.markAsRead(content.id) },
                                        onToggleFavorite: { await viewModel.toggleFavorite(content.id) },
                                        onToggleUnlike: { await viewModel.toggleUnlike(content.id) }
                                    )
                                }
                                .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                                .listRowSeparator(.hidden)
                                .listRowBackground(Color.clear)
                            }
                        }
                        .listStyle(.plain)
                        .refreshable {
                            await viewModel.refresh()
                        }
                    }
                }
                .task {
                    viewModel.selectedContentType = "news"
                    viewModel.selectedReadFilter = settings.showReadContent ? "all" : "unread"
                    await viewModel.loadContent()
                }
                .onChange(of: settings.showReadContent) { _, showRead in
                    viewModel.selectedReadFilter = showRead ? "all" : "unread"
                }
            }
        }
    }
}

#Preview {
    NewsView()
}
