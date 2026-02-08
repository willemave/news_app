//
//  LongFormView.swift
//  newsly
//
//  Created by Assistant on 11/4/25.
//

import SwiftUI

struct LongFormView: View {
    @ObservedObject var viewModel: LongContentListViewModel
    let onSelect: (ContentDetailRoute) -> Void

    @ObservedObject private var settings = AppSettings.shared
    @StateObject private var processingCountService = ProcessingCountService.shared
    @State private var showMarkAllConfirmation = false
    @State private var isProcessingBulk = false

    var body: some View {
        ZStack {
            VStack(spacing: 0) {
                if viewModel.state == .initialLoading && viewModel.currentItems().isEmpty {
                    LoadingView()
                } else if case .error(let error) = viewModel.state, viewModel.currentItems().isEmpty {
                    ErrorView(message: error.localizedDescription) {
                        viewModel.refreshTrigger.send(())
                    }
                } else {
                    if viewModel.currentItems().isEmpty {
                        longFormEmptyState
                    } else {
                        List {
                            ForEach(viewModel.currentItems(), id: \.id) { content in
                                VStack(spacing: 0) {
                                    NavigationLink(
                                        value: ContentDetailRoute(
                                            summary: content,
                                            allContentIds: viewModel.currentItems().map(\.id)
                                        )
                                    ) {
                                        ContentCard(content: content)
                                    }

                                    downloadMoreRow(for: content)
                                }
                                .listRowInsets(EdgeInsets(top: 0, leading: 8, bottom: 0, trailing: 8))
                                .listRowSeparator(.hidden)
                                .swipeActions(edge: .leading, allowsFullSwipe: true) {
                                    if !content.isRead {
                                        Button {
                                            viewModel.markAsRead(content.id)
                                        } label: {
                                            Label("Mark as Read", systemImage: "checkmark.circle.fill")
                                        }
                                        .tint(.green)
                                    }
                                }
                                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                                    Button {
                                        Task {
                                            await viewModel.toggleFavorite(content.id)
                                        }
                                    } label: {
                                        Label(
                                            content.isFavorited ? "Unfavorite" : "Favorite",
                                            systemImage: content.isFavorited ? "star.slash" : "star"
                                        )
                                    }
                                    .tint(content.isFavorited ? .gray : .yellow)
                                }
                                .onAppear {
                                    if content.id == viewModel.currentItems().last?.id {
                                        viewModel.loadMoreTrigger.send(())
                                    }
                                }
                            }

                            if viewModel.state == .loadingMore {
                                HStack {
                                    Spacer()
                                    ProgressView()
                                        .padding()
                                    Spacer()
                                }
                                .listRowInsets(EdgeInsets())
                                .listRowSeparator(.hidden)
                                .listRowBackground(Color.clear)
                            }
                        }
                        .listStyle(.plain)
                        .padding(.top, 8)
                        .navigationBarHidden(true)
                        .refreshable {
                            viewModel.refreshTrigger.send(())
                            await processingCountService.refreshCount()
                        }
                        .simultaneousGesture(
                            LongPressGesture(minimumDuration: 0.8).onEnded { _ in
                                if viewModel.currentItems().contains(where: { !$0.isRead }) {
                                    showMarkAllConfirmation = true
                                }
                            }
                        )
                        .confirmationDialog(
                            "Mark all long-form content as read?",
                            isPresented: $showMarkAllConfirmation
                        ) {
                            Button("Mark All as Read", role: .destructive) {
                                showMarkAllConfirmation = false
                                isProcessingBulk = true
                                Task {
                                    defer { isProcessingBulk = false }
                                    await viewModel.markAllVisibleAsRead()
                                }
                            }
                            Button("Cancel", role: .cancel) {
                                showMarkAllConfirmation = false
                            }
                        } message: {
                            Text("Long press to quickly mark every unread item in the current list as read.")
                        }
                    }
                }
            }
            .onAppear {
                viewModel.setReadFilter(settings.showReadContent ? .all : .unread)
                viewModel.refreshTrigger.send(())
                Task {
                    await processingCountService.refreshCount()
                }
            }
            .onChange(of: settings.showReadContent) { _, showRead in
                viewModel.setReadFilter(showRead ? .all : .unread)
            }

            if isProcessingBulk {
                Color.black.opacity(0.15)
                    .ignoresSafeArea()
                ProgressView("Marking content")
                    .padding(16)
                    .background(Color(.systemBackground))
                    .cornerRadius(12)
            }
        }
    }

    @ViewBuilder
    private func downloadMoreRow(for content: ContentSummary) -> some View {
        if content.contentTypeEnum == .article || content.contentTypeEnum == .podcast {
            HStack {
                DownloadMoreMenu(title: "Download more") { count in
                    Task { await viewModel.downloadMoreFromSeries(contentId: content.id, count: count) }
                }
                Spacer()
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 8)
        }
    }

    @ViewBuilder
    private var longFormEmptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "doc.richtext")
                .font(.largeTitle)
                .foregroundColor(.secondary)
            if processingCountService.longFormProcessingCount > 0 {
                ProgressView()
                Text("Preparing \(processingCountService.longFormProcessingCount) long-form items")
                    .foregroundColor(.secondary)
            } else {
                Text("No long-form content found.")
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
