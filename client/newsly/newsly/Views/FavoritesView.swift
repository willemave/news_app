//
//  FavoritesView.swift
//  newsly
//
//  Created by Assistant on 8/9/25.
//

import SwiftUI

struct FavoritesView: View {
    @StateObject private var viewModel = ContentListViewModel()
    @ObservedObject private var settings = AppSettings.shared
    @State private var showingFilters = false
    
    var body: some View {
        NavigationStack {
            ZStack {
                VStack(spacing: 0) {
                    if viewModel.isLoading && viewModel.contents.isEmpty {
                        LoadingView()
                    } else if let error = viewModel.errorMessage, viewModel.contents.isEmpty {
                        ErrorView(message: error) {
                            Task { await viewModel.loadFavorites() }
                        }
                    } else {
                        // Content List
                        if viewModel.contents.isEmpty {
                            VStack(spacing: 16) {
                                Spacer()
                                Image(systemName: "star.slash")
                                    .font(.largeTitle)
                                    .foregroundColor(.secondary)
                                Text("No favorites yet.")
                                    .foregroundColor(.secondary)
                                Text("Swipe right on articles or podcasts to add them to your favorites.")
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
                                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                        Button {
                                            Task {
                                                await viewModel.toggleFavorite(content.id)
                                                // Remove from list after unfavoriting with animation
                                                withAnimation(.easeOut(duration: 0.3)) {
                                                    viewModel.contents.removeAll { $0.id == content.id }
                                                }
                                            }
                                        } label: {
                                            Label("Remove from Favorites", systemImage: "star.slash.fill")
                                        }
                                        .tint(.red)
                                    }
                                }
                            }
                            .listStyle(.plain)
                            .refreshable {
                                await viewModel.loadFavorites()
                            }
                        }
                    }
                }
                .task {
                    await viewModel.loadFavorites()
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
                        Task { await viewModel.loadFavorites() }
                    }
                }
            }
        }
    }
}

#Preview {
    FavoritesView()
}
