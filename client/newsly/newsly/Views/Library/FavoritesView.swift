//
//  FavoritesView.swift
//  newsly
//

import SwiftUI

struct FavoritesView: View {
    let showNavigationTitle: Bool

    @StateObject private var viewModel = ContentListViewModel(defaultReadFilter: "all")

    init(showNavigationTitle: Bool = true) {
        self.showNavigationTitle = showNavigationTitle
    }

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
        .navigationTitle(showNavigationTitle ? "Favorites" : "")
        .task { await viewModel.loadFavorites() }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 20) {
            Image(systemName: "star")
                .font(.system(size: 48, weight: .light))
                .foregroundStyle(Color.accentColor.opacity(0.7))

            VStack(spacing: 6) {
                Text("No favorites yet")
                    .font(.listTitle.weight(.semibold))
                    .foregroundStyle(Color.textPrimary)

                Text("Swipe right on articles or podcasts to add them to your favorites.")
                    .font(.listSubtitle)
                    .foregroundStyle(Color.textSecondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 280)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.surfacePrimary)
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
                .appListRow()
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

            if viewModel.isLoadingMore {
                HStack {
                    Spacer()
                    ProgressView()
                        .padding()
                    Spacer()
                }
                .appListRow()
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
            thumbnailView

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
        }
        .appRow(.regular)
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
                    .frame(width: RowMetrics.thumbnailSize, height: RowMetrics.thumbnailSize)
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
            .frame(width: RowMetrics.thumbnailSize, height: RowMetrics.thumbnailSize)
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
