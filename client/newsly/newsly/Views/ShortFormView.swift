//
//  ShortFormView.swift
//  newsly
//
//  Created by Assistant on 11/4/25.
//

import os.log
import SwiftUI

private let logger = Logger(subsystem: "com.newsly", category: "ShortFormView")

struct ShortFormView: View {
    @ObservedObject var viewModel: ShortNewsListViewModel
    let onSelect: (ContentDetailRoute) -> Void
    @StateObject private var processingCountService = ProcessingCountService.shared

    /// Track which items have already been marked as read to avoid duplicates
    @State private var markedAsReadIds: Set<Int> = []
    @State private var showMarkAllConfirmation = false
    @State private var topVisibleItemId: Int?

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                if case .error(let error) = viewModel.state, viewModel.currentItems().isEmpty {
                    ErrorView(message: error.localizedDescription) {
                        viewModel.refreshTrigger.send(())
                    }
                    .padding(.top, 48)
                } else if viewModel.state == .initialLoading, viewModel.currentItems().isEmpty {
                    ProgressView("Loading")
                        .padding(.top, 48)
                } else if viewModel.currentItems().isEmpty {
                    shortFormEmptyState
                } else {
                    ForEach(viewModel.currentItems(), id: \.id) { item in
                        ShortNewsRow(item: item)
                            .id(item.id)
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
            .scrollTargetLayout()
            .padding(.horizontal, 24)
            .padding(.top, 20)
        }
        .scrollPosition(id: $topVisibleItemId, anchor: .top)
        .onChange(of: topVisibleItemId) { _, _ in
            markItemsAboveAsRead()
        }
        .onScrollPhaseChange { _, newPhase in
            guard newPhase == .idle else { return }
            markItemsAboveAsRead()
        }
        .refreshable {
            viewModel.refreshTrigger.send(())
            await processingCountService.refreshCount()
        }
        .onAppear {
            if viewModel.currentItems().isEmpty {
                viewModel.refreshTrigger.send(())
            }
            Task {
                await processingCountService.refreshCount()
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

    private func markItemsAboveAsRead() {
        guard let topVisibleItemId else { return }
        let items = viewModel.currentItems()
        guard let index = items.firstIndex(where: { $0.id == topVisibleItemId }) else { return }

        let idsToMark = items.prefix(index)
            .filter { !$0.isRead && !markedAsReadIds.contains($0.id) }
            .map(\.id)

        guard !idsToMark.isEmpty else { return }

        logger.info("[ShortFormView] Items scrolled past top | ids=\(idsToMark, privacy: .public)")
        idsToMark.forEach { markedAsReadIds.insert($0) }
        viewModel.itemsScrolledPastTop(ids: idsToMark)
    }

    @ViewBuilder
    private var shortFormEmptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "bolt.fill")
                .font(.largeTitle)
                .foregroundColor(.secondary)
            if processingCountService.newsProcessingCount > 0 {
                ProgressView()
                Text("Preparing \(processingCountService.newsProcessingCount) short-form items")
                    .foregroundColor(.secondary)
            } else {
                Text("No short-form content found.")
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }
}

private struct ShortNewsRow: View {
    let item: ContentSummary

    private let thumbnailSize: CGFloat = 60

    private var hasImage: Bool {
        let displayUrl = item.thumbnailUrl ?? item.imageUrl
        guard let urlString = displayUrl,
              urlString.count > 1
        else { return false }
        return buildImageURL(from: urlString) != nil
    }

    private var titleWeight: Font.Weight {
        item.isRead ? .regular : .semibold
    }

    private var titleColor: Color {
        item.isRead ? .secondary : .primary
    }

    /// Platform-specific accent color for badges
    private var platformColor: Color {
        guard let platform = item.platform?.lowercased() else {
            return .gray
        }
        switch platform {
        case "hacker news", "hackernews", "hn":
            return .orange
        case "reddit":
            return Color(red: 1.0, green: 0.45, blue: 0.0) // Reddit orange-red
        case "twitter", "x":
            return .blue
        case "lobsters":
            return .red
        default:
            return .gray
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 12) {
                // Thumbnail only when image exists
                if hasImage {
                    thumbnailView
                        .shadow(color: .black.opacity(0.08), radius: 3, x: 0, y: 1)
                }

                // Text content
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.displayTitle)
                        .font(.body)
                        .fontWeight(titleWeight)
                        .foregroundColor(titleColor)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)

                    if let summary = item.shortSummary, !summary.isEmpty {
                        Text(summary)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .lineLimit(2)
                    }

                    HStack(spacing: 6) {
                        if let source = item.source {
                            Text(source)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        if let time = item.relativeTimeDisplay {
                            Text("·")
                                .font(.caption)
                                .foregroundColor(Color(.quaternaryLabel))
                            Text(time)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        if let platform = item.platform {
                            Text(platform)
                                .font(.caption2)
                                .foregroundColor(platformColor.opacity(item.isRead ? 0.6 : 0.9))
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(platformColor.opacity(item.isRead ? 0.08 : 0.15))
                                .clipShape(Capsule())
                        }
                    }
                }
            }

            Divider()
                .padding(.leading, hasImage ? 72 : 0)
        }
        .padding(.vertical, 10)
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
