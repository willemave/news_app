//
//  ShortFormView.swift
//  newsly
//
//  Created by Assistant on 11/4/25.
//

import os.log
import SwiftUI

private let logger = Logger(subsystem: "com.newsly", category: "ShortFormView")

/// Preference key to collect items that have scrolled past the top
private struct ScrolledPastTopPreferenceKey: PreferenceKey {
    static var defaultValue: [Int] = []
    static func reduce(value: inout [Int], nextValue: () -> [Int]) {
        value.append(contentsOf: nextValue())
    }
}

struct ShortFormView: View {
    @ObservedObject var viewModel: ShortNewsListViewModel
    let onSelect: (ContentDetailRoute) -> Void

    /// Track which items have already been marked as read to avoid duplicates
    @State private var markedAsReadIds: Set<Int> = []
    @State private var showMarkAllConfirmation = false

    var body: some View {
        ScrollViewReader { _ in
            ScrollView {
                LazyVStack(spacing: 12) {
                    if case .error(let error) = viewModel.state, viewModel.currentItems().isEmpty {
                        ErrorView(message: error.localizedDescription) {
                            viewModel.refreshTrigger.send(())
                        }
                        .padding(.top, 48)
                    } else if viewModel.state == .initialLoading, viewModel.currentItems().isEmpty {
                        ProgressView("Loading")
                            .padding(.top, 48)
                    } else if viewModel.currentItems().isEmpty {
                        VStack(spacing: 16) {
                            Spacer()
                            Image(systemName: "bolt.fill")
                                .font(.largeTitle)
                                .foregroundColor(.secondary)
                            Text("No short-form content found.")
                                .foregroundColor(.secondary)
                            Spacer()
                        }
                        .frame(maxWidth: .infinity)
                    } else {
                        ForEach(viewModel.currentItems(), id: \.id) { item in
                            ShortNewsRow(item: item)
                                .background(
                                    ScrollPositionDetector(
                                        itemId: item.id,
                                        isAlreadyMarked: markedAsReadIds.contains(item.id) || item.isRead
                                    )
                                )
                                .onTapGesture {
                                    let ids = viewModel.currentItems().map(\.id)
                                    let route = ContentDetailRoute(
                                        contentId: item.id,
                                        contentType: item.contentTypeEnum ?? .news,
                                        allContentIds: ids
                                    )
                                    onSelect(route)
                                }
                                .onAppear {
                                    if item.id == viewModel.currentItems().last?.id {
                                        viewModel.loadMoreTrigger.send(())
                                    }
                                }
                        }

                        if viewModel.currentItems().contains(where: { !$0.isRead }) {
                            Button {
                                showMarkAllConfirmation = true
                            } label: {
                                Text("Mark All as Read")
                                    .font(.subheadline.weight(.semibold))
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                                    .background(Color.secondary.opacity(0.12))
                                    .clipShape(RoundedRectangle(cornerRadius: 12))
                            }
                            .buttonStyle(.plain)
                            .padding(.vertical, 8)
                        }

                        if viewModel.state == .loadingMore {
                            ProgressView()
                                .padding(.vertical, 16)
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
            }
            .coordinateSpace(name: "scrollView")
            .onPreferenceChange(ScrolledPastTopPreferenceKey.self) { ids in
                // Filter out items we've already processed
                let newIds = ids.filter { !markedAsReadIds.contains($0) }
                guard !newIds.isEmpty else { return }

                logger.info("[ShortFormView] Items scrolled past top | ids=\(newIds, privacy: .public)")

                // Add to our tracking set
                for id in newIds {
                    markedAsReadIds.insert(id)
                }

                // Notify view model
                viewModel.itemsScrolledPastTop(ids: newIds)
            }
            .refreshable {
                viewModel.refreshTrigger.send(())
            }
            .onAppear {
                if viewModel.currentItems().isEmpty {
                    viewModel.refreshTrigger.send(())
                }
            }
            .confirmationDialog(
                "Mark all news items as read?",
                isPresented: $showMarkAllConfirmation
            ) {
                Button("Mark All as Read", role: .destructive) {
                    showMarkAllConfirmation = false
                    viewModel.markAllVisibleAsRead()
                }
                Button("Cancel", role: .cancel) {
                    showMarkAllConfirmation = false
                }
            } message: {
                Text("Marks every unread item currently loaded in the list.")
            }
        }
    }
}

/// Detects when an item's bottom edge scrolls past the top of the screen
private struct ScrollPositionDetector: View {
    let itemId: Int
    let isAlreadyMarked: Bool

    var body: some View {
        GeometryReader { geo in
            let frame = geo.frame(in: .named("scrollView"))
            // Item has scrolled past top when its bottom edge is above the top of the scroll view
            // We use a small threshold (50pt) to ensure the item has clearly scrolled off
            let hasScrolledPastTop = frame.maxY < 50

            Color.clear
                .preference(
                    key: ScrolledPastTopPreferenceKey.self,
                    value: (hasScrolledPastTop && !isAlreadyMarked) ? [itemId] : []
                )
        }
    }
}

private struct ShortNewsRow: View {
    let item: ContentSummary

    private let thumbnailSize: CGFloat = 60

    private var textOpacity: Double {
        item.isRead ? 0.5 : 1.0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 12) {
                // Thumbnail on left
                thumbnailView

                // Text content
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.displayTitle)
                        .font(.headline)
                        .foregroundColor(.primary.opacity(textOpacity))
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)

                    if let summary = item.shortSummary, !summary.isEmpty {
                        Text(summary)
                            .font(.subheadline)
                            .foregroundColor(.secondary.opacity(textOpacity))
                            .lineLimit(2)
                    }

                    HStack(spacing: 6) {
                        if let source = item.source {
                            Text(source)
                                .font(.caption)
                                .foregroundColor(.secondary.opacity(textOpacity))
                        }
                        if let platform = item.platform {
                            Text(platform)
                                .font(.caption2)
                                .foregroundColor(.secondary.opacity(textOpacity))
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.gray.opacity(item.isRead ? 0.05 : 0.1))
                                .clipShape(Capsule())
                        }
                    }
                }
            }

            Divider()
        }
        .padding(.vertical, 8)
    }

    @ViewBuilder
    private var thumbnailView: some View {
        // Prefer thumbnail URL for faster loading, fall back to full image
        let displayUrl = item.thumbnailUrl ?? item.imageUrl
        if let imageUrlString = displayUrl,
           let imageUrl = buildImageURL(from: imageUrlString) {
            CachedAsyncImage(url: imageUrl) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: thumbnailSize, height: thumbnailSize)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } placeholder: {
                ProgressView()
                    .frame(width: thumbnailSize, height: thumbnailSize)
            }
        } else {
            thumbnailPlaceholder
        }
    }

    private var thumbnailPlaceholder: some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(Color.secondary.opacity(0.15))
            .frame(width: thumbnailSize, height: thumbnailSize)
            .overlay(
                Image(systemName: "newspaper")
                    .font(.system(size: 20))
                    .foregroundColor(.secondary.opacity(0.6))
            )
    }

    private func buildImageURL(from urlString: String) -> URL? {
        if urlString.hasPrefix("http://") || urlString.hasPrefix("https://") {
            return URL(string: urlString)
        }
        // Use string concatenation instead of appendingPathComponent to preserve path structure
        let baseURL = AppSettings.shared.baseURL
        let fullURL = urlString.hasPrefix("/") ? baseURL + urlString : baseURL + "/" + urlString
        return URL(string: fullURL)
    }
}
