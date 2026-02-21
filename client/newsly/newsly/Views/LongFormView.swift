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
                        ScrollView {
                            LazyVStack(spacing: CardMetrics.cardSpacing) {
                                ForEach(viewModel.currentItems(), id: \.id) { content in
                                    NavigationLink(
                                        value: ContentDetailRoute(
                                            summary: content,
                                            allContentIds: viewModel.currentItems().map(\.id)
                                        )
                                    ) {
                                        LongFormCard(
                                            content: content,
                                            onMarkRead: {
                                                viewModel.markAsRead(content.id)
                                            },
                                            onToggleFavorite: {
                                                Task {
                                                    await viewModel.toggleFavorite(content.id)
                                                }
                                            }
                                        )
                                    }
                                    .buttonStyle(.plain)
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
                                }
                            }
                            .padding(.horizontal, 24)
                            .padding(.vertical, 24)
                        }
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
    private var longFormEmptyState: some View {
        if processingCountService.longFormProcessingCount > 0 {
            VStack(spacing: 16) {
                Spacer()
                ProgressView()
                Text("Preparing \(processingCountService.longFormProcessingCount) long-form items")
                    .font(.listSubtitle)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            EmptyStateView(
                icon: "doc.richtext",
                title: "No Long-Form Content",
                subtitle: "Articles and podcasts will appear here once processed"
            )
        }
    }
}
