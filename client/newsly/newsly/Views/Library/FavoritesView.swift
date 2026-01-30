//
//  FavoritesView.swift
//  newsly
//

import SwiftUI

struct FavoritesView: View {
    @StateObject private var viewModel = ContentListViewModel(defaultReadFilter: "all")
    @State private var showingFilters = false

    var body: some View {
        Group {
            if viewModel.isLoading && viewModel.contents.isEmpty {
                LoadingView()
            } else if let error = viewModel.errorMessage, viewModel.contents.isEmpty {
                ErrorView(message: error) {
                    Task { await viewModel.loadFavorites() }
                }
            } else if viewModel.contents.isEmpty {
                emptyState
            } else {
                contentList
            }
        }
        .background(Color.surfacePrimary)
        .navigationTitle("Favorites")
        .task { await viewModel.loadFavorites() }
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

    // MARK: - Empty State

    private var emptyState: some View {
        SettingsEmptyStateView(
            icon: "star",
            title: "No Favorites",
            subtitle: "Swipe right on articles or podcasts to add them to your favorites"
        )
    }

    // MARK: - Content List

    private var contentList: some View {
        List {
            ForEach(viewModel.contents) { content in
                NavigationLink(destination: ContentDetailView(
                    contentId: content.id,
                    allContentIds: viewModel.contents.map(\.id)
                )) {
                    FavoriteRow(content: content)
                }
                .listRowInsets(EdgeInsets(top: 0, leading: 0, bottom: 0, trailing: 0))
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
                .swipeActions(edge: .leading, allowsFullSwipe: true) {
                    if !content.isRead {
                        Button {
                            Task { await viewModel.markAsRead(content.id) }
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
                            withAnimation(.easeOut(duration: 0.3)) {
                                viewModel.contents.removeAll { $0.id == content.id }
                            }
                        }
                    } label: {
                        Label("Remove", systemImage: "star.slash")
                    }
                    .tint(.red)
                }
                .onAppear {
                    if content.id == viewModel.contents.last?.id {
                        Task { await viewModel.loadMoreContent() }
                    }
                }
            }

            // Loading more indicator
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
        .refreshable { await viewModel.loadFavorites() }
    }
}

// MARK: - Favorite Row

private struct FavoriteRow: View {
    let content: ContentSummary

    private var textOpacity: Double {
        content.isRead ? 0.6 : 1.0
    }

    var body: some View {
        HStack(spacing: 12) {
            // Thumbnail
            thumbnailView

            // Content
            VStack(alignment: .leading, spacing: 4) {
                Text(content.displayTitle)
                    .font(.listTitle)
                    .foregroundStyle(Color.textPrimary.opacity(textOpacity))
                    .lineLimit(2)

                HStack(spacing: 6) {
                    if let source = content.source {
                        Text(source)
                            .font(.listCaption)
                            .foregroundStyle(Color.textTertiary)
                            .lineLimit(1)
                    }

                    if let date = content.processedDateDisplay {
                        Text("·")
                            .font(.listCaption)
                            .foregroundStyle(Color.textTertiary)

                        Text(date)
                            .font(.listCaption)
                            .foregroundStyle(Color.textTertiary)
                    }
                }
            }

            Spacer(minLength: 8)

            // Chevron
            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Color.textTertiary)
        }
        .padding(.vertical, Spacing.rowVertical)
        .padding(.horizontal, Spacing.rowHorizontal)
        .contentShape(Rectangle())
    }

    // MARK: - Thumbnail

    @ViewBuilder
    private var thumbnailView: some View {
        let displayUrl = content.thumbnailUrl ?? content.imageUrl
        if let imageUrlString = displayUrl,
           let imageUrl = buildImageURL(from: imageUrlString) {
            CachedAsyncImage(url: imageUrl) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: 56, height: 56)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } placeholder: {
                thumbnailPlaceholder
            }
        } else {
            thumbnailPlaceholder
        }
    }

    private var thumbnailPlaceholder: some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(Color.surfaceSecondary)
            .frame(width: 56, height: 56)
            .overlay(
                Image(systemName: contentTypeIcon)
                    .font(.system(size: 20))
                    .foregroundStyle(Color.textTertiary)
            )
    }

    private var contentTypeIcon: String {
        switch content.contentTypeEnum {
        case .article: return "doc.text"
        case .podcast: return "headphones"
        case .news: return "newspaper"
        default: return "doc"
        }
    }

    private func buildImageURL(from urlString: String) -> URL? {
        if urlString.hasPrefix("http://") || urlString.hasPrefix("https://") {
            return URL(string: urlString)
        }
        let baseURL = AppSettings.shared.baseURL
        let fullURL = urlString.hasPrefix("/") ? baseURL + urlString : baseURL + "/" + urlString
        return URL(string: fullURL)
    }
}
