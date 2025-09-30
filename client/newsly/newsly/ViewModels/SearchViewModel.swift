//
//  SearchViewModel.swift
//  newsly
//
//  Created by Assistant on 9/15/25.
//

import Foundation
import Combine

@MainActor
class SearchViewModel: ObservableObject {
    @Published var searchText: String = ""
    @Published var selectedContentType: String = "all"
    @Published var results: [ContentSummary] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var hasSearched: Bool = false

    private let service = ContentService.shared
    private var cancellables = Set<AnyCancellable>()
    private var searchTask: Task<Void, Never>?

    let contentTypeOptions: [(String, String)] = [
        ("all", "All"),
        ("article", "Articles"),
        ("podcast", "Podcasts")
    ]

    init() {
        $searchText
            .debounce(for: .milliseconds(500), scheduler: RunLoop.main)
            .removeDuplicates()
            .sink { [weak self] text in
                self?.performSearch(text)
            }
            .store(in: &cancellables)

        $selectedContentType
            .dropFirst()
            .sink { [weak self] _ in
                guard let self else { return }
                if self.hasSearched, self.searchText.count >= 2 {
                    self.performSearch(self.searchText)
                }
            }
            .store(in: &cancellables)
    }

    func retrySearch() {
        performSearch(searchText)
    }

    private func performSearch(_ query: String) {
        searchTask?.cancel()
        guard query.trimmingCharacters(in: .whitespacesAndNewlines).count >= 2 else {
            results = []
            hasSearched = false
            errorMessage = nil
            return
        }
        searchTask = Task { [weak self] in
            await self?.runSearch(query: query)
        }
    }

    private func runSearch(query: String) async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await service.searchContent(
                query: query,
                contentType: selectedContentType,
                limit: 25,
                cursor: nil
            )
            if !Task.isCancelled {
                results = response.contents
                hasSearched = true
            }
        } catch {
            if !Task.isCancelled {
                errorMessage = error.localizedDescription
                results = []
                hasSearched = true
            }
        }
        isLoading = false
    }

    // Optional actions to keep cards interactive
    func markAsRead(_ id: Int) async {
        do {
            try await service.markContentAsRead(id: id)
            if let i = results.firstIndex(where: { $0.id == id }) {
                let c = results[i]
                results[i] = ContentSummary(
                    id: c.id, contentType: c.contentType, url: c.url, title: c.title,
                    source: c.source, platform: c.platform, status: c.status,
                    shortSummary: c.shortSummary, createdAt: c.createdAt, processedAt: c.processedAt,
                    classification: c.classification, publicationDate: c.publicationDate,
                    isRead: true, isFavorited: c.isFavorited, isUnliked: c.isUnliked,
                    isAggregate: c.isAggregate, itemCount: c.itemCount
                )
            }
        } catch {
            errorMessage = "Failed to mark as read"
        }
    }

    func toggleFavorite(_ id: Int) async {
        do {
            let response = try await service.toggleFavorite(id: id)
            if let isFav = response["is_favorited"] as? Bool,
               let i = results.firstIndex(where: { $0.id == id }) {
                var c = results[i]
                c.isFavorited = isFav
                results[i] = c
            }
        } catch {
            errorMessage = "Failed to update favorite"
        }
    }

    func toggleUnlike(_ id: Int) async {
        do {
            let response = try await service.toggleUnlike(id: id)
            if let i = results.firstIndex(where: { $0.id == id }) {
                var c = results[i]
                c.isUnliked = (response["is_unliked"] as? Bool) ?? c.isUnliked
                if let isRead = response["is_read"] as? Bool, isRead {
                    c = ContentSummary(
                        id: c.id, contentType: c.contentType, url: c.url, title: c.title,
                        source: c.source, platform: c.platform, status: c.status,
                        shortSummary: c.shortSummary, createdAt: c.createdAt, processedAt: c.processedAt,
                        classification: c.classification, publicationDate: c.publicationDate,
                        isRead: true, isFavorited: c.isFavorited, isUnliked: c.isUnliked,
                        isAggregate: c.isAggregate, itemCount: c.itemCount
                    )
                }
                results[i] = c
            }
        } catch {
            errorMessage = "Failed to update unlike"
        }
    }
}
