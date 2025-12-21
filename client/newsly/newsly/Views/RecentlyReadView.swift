//
//  RecentlyReadView.swift
//  newsly
//
//  Created by Assistant on 9/29/25.
//

import SwiftUI

struct RecentlyReadView: View {
    @StateObject private var viewModel = ContentListViewModel()
    @ObservedObject private var settings = AppSettings.shared
    @State private var showingFilters = false

    var body: some View {
        ZStack {
            VStack(spacing: 0) {
                if viewModel.isLoading && viewModel.contents.isEmpty {
                    LoadingView()
                } else if let error = viewModel.errorMessage, viewModel.contents.isEmpty {
                    ErrorView(message: error) {
                        Task { await viewModel.loadRecentlyRead() }
                    }
                } else {
                    // Content List
                    if viewModel.contents.isEmpty {
                        VStack(spacing: 16) {
                            Spacer()
                            Image(systemName: "clock.badge.questionmark")
                                .font(.largeTitle)
                                .foregroundColor(.secondary)
                            Text("No recently read items yet.")
                                .foregroundColor(.secondary)
                            Text("Items you've read will appear here, sorted by most recently read.")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 40)
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

                                    ContentCard(content: content)
                                }
                                .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                                .listRowSeparator(.hidden)
                                .listRowBackground(Color.clear)
                                .swipeActions(edge: .leading, allowsFullSwipe: true) {
                                    Button {
                                        Task {
                                            // Mark as unread and remove from recently read list
                                            try? await ContentService.shared.markContentAsUnread(id: content.id)
                                            // Remove from list with animation
                                            withAnimation(.easeOut(duration: 0.3)) {
                                                viewModel.contents.removeAll { $0.id == content.id }
                                            }
                                        }
                                    } label: {
                                        Label("Mark as Unread", systemImage: "circle")
                                    }
                                    .tint(.orange)
                                }
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button {
                                        Task {
                                            await viewModel.toggleFavorite(content.id)
                                        }
                                    } label: {
                                        Label(content.isFavorited ? "Remove from Favorites" : "Add to Favorites",
                                              systemImage: content.isFavorited ? "star.slash.fill" : "star.fill")
                                    }
                                    .tint(content.isFavorited ? .red : .yellow)
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
                        .refreshable {
                            await viewModel.loadRecentlyRead()
                        }
                    }
                }
            }
            .task {
                await viewModel.loadRecentlyRead()
            }
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showingFilters = true
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                    }
                    .accessibilityLabel("Filters")
                }
            }
            .sheet(isPresented: $showingFilters) {
                FilterSheet(
                    selectedContentType: $viewModel.selectedContentType,
                    selectedDate: $viewModel.selectedDate,
                    selectedReadFilter: $viewModel.selectedReadFilter,
                    isPresented: $showingFilters,
                    contentTypes: viewModel.contentTypes,
                    availableDates: viewModel.availableDates
                )
                .onDisappear {
                    Task { await viewModel.loadRecentlyRead() }
                }
            }
        }
        .navigationTitle("Recently Read")
    }
}

#Preview {
    RecentlyReadView()
}