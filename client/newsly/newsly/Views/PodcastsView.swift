//
//  PodcastsView.swift
//  newsly
//
//  Created by Assistant on 7/20/25.
//

import SwiftUI

struct PodcastsView: View {
    @StateObject private var viewModel = ContentListViewModel()
    @ObservedObject private var settings = AppSettings.shared
    @State private var showMarkAllConfirmation = false
    @State private var isProcessingBulk = false
    
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
                    } else {
                        // Content List
                        if viewModel.contents.isEmpty {
                            VStack(spacing: 16) {
                                Spacer()
                                Image(systemName: "mic.circle")
                                    .font(.largeTitle)
                                    .foregroundColor(.secondary)
                                Text("No podcasts found.")
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
                                        )) {
                                            EmptyView()
                                        }
                                        .opacity(0)
                                        .buttonStyle(PlainButtonStyle())

                                        ContentCard(
                                            content: content,
                                            onMarkAsRead: { await viewModel.markAsRead(content.id) },
                                            onToggleFavorite: { await viewModel.toggleFavorite(content.id) }
                                        )
                                    }
                                    .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                                    .listRowSeparator(.hidden)
                                    .listRowBackground(Color.clear)
                                    .swipeActions(edge: .leading, allowsFullSwipe: true) {
                                        if !content.isRead {
                                            Button {
                                                Task {
                                                    await viewModel.markAsRead(content.id)
                                                }
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
                                            Label(content.isFavorited ? "Unfavorite" : "Favorite",
                                                  systemImage: content.isFavorited ? "star.slash.fill" : "star.fill")
                                        }
                                        .tint(content.isFavorited ? .gray : .yellow)
                                    }
                                    .onAppear {
                                        // Load more content when reaching near the end
                                        if content.id == viewModel.contents.last?.id {
                                            Task {
                                                await viewModel.loadMoreContent()
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
                                    .listRowInsets(EdgeInsets())
                                    .listRowSeparator(.hidden)
                                    .listRowBackground(Color.clear)
                                }
                            }
                            .listStyle(.plain)
                            .navigationBarHidden(true)
                            .refreshable {
                                await viewModel.refresh()
                            }
                            .simultaneousGesture(
                                LongPressGesture(minimumDuration: 0.8).onEnded { _ in
                                    if viewModel.contents.contains(where: { !$0.isRead }) {
                                        showMarkAllConfirmation = true
                                    }
                                }
                            )
                            .confirmationDialog(
                                "Mark all podcasts as read?",
                                isPresented: $showMarkAllConfirmation
                            ) {
                                Button("Mark All as Read", role: .destructive) {
                                    showMarkAllConfirmation = false
                                    Task {
                                        isProcessingBulk = true
                                        defer { isProcessingBulk = false }
                                        await viewModel.markAllAsRead()
                                    }
                                }
                                Button("Cancel", role: .cancel) {
                                    showMarkAllConfirmation = false
                                }
                            } message: {
                                Text("Long press anywhere on the list to mark all visible podcasts as read.")
                            }
                        }
                    }
                }
                .task {
                    viewModel.selectedContentType = "podcast"
                    viewModel.selectedReadFilter = settings.showReadContent ? "all" : "unread"
                    await viewModel.loadContent()
                }
                .onChange(of: settings.showReadContent) { _, showRead in
                    viewModel.selectedReadFilter = showRead ? "all" : "unread"
                }
                
                if isProcessingBulk {
                    Color.black.opacity(0.15)
                        .ignoresSafeArea()
                    ProgressView("Marking podcasts")
                        .padding(16)
                        .background(Color(.systemBackground))
                        .cornerRadius(12)
                }
            }
        }
    }
}
