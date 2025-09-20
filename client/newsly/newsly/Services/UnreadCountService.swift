//
//  UnreadCountService.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

@MainActor
class UnreadCountService: ObservableObject {
    static let shared = UnreadCountService()
    
    @Published var articleCount: Int = 0
    @Published var podcastCount: Int = 0
    @Published var newsCount: Int = 0
    
    private let client = APIClient.shared
    private var refreshTimer: Timer?
    
    private init() {
        // Start periodic refresh
        startPeriodicRefresh()
    }
    
    deinit {
        refreshTimer?.invalidate()
    }
    
    func refreshCounts() async {
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await self.fetchArticleCount() }
            group.addTask { await self.fetchPodcastCount() }
            group.addTask { await self.fetchNewsCount() }
        }
    }
    
    private func fetchArticleCount() async {
        do {
            let response: ContentListResponse = try await client.request(
                APIEndpoints.contentList,
                queryItems: [
                    URLQueryItem(name: "content_type", value: "article"),
                    URLQueryItem(name: "read_filter", value: "unread")
                ]
            )
            articleCount = response.total
        } catch {
            print("Failed to fetch article count: \(error)")
        }
    }
    
    private func fetchPodcastCount() async {
        do {
            let response: ContentListResponse = try await client.request(
                APIEndpoints.contentList,
                queryItems: [
                    URLQueryItem(name: "content_type", value: "podcast"),
                    URLQueryItem(name: "read_filter", value: "unread")
                ]
            )
            podcastCount = response.total
        } catch {
            print("Failed to fetch podcast count: \(error)")
        }
    }

    private func fetchNewsCount() async {
        do {
            let response: ContentListResponse = try await client.request(
                APIEndpoints.contentList,
                queryItems: [
                    URLQueryItem(name: "content_type", value: "news"),
                    URLQueryItem(name: "read_filter", value: "unread")
                ]
            )
            newsCount = response.total
        } catch {
            print("Failed to fetch news count: \(error)")
        }
    }
    
    private func startPeriodicRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { _ in
            Task {
                await self.refreshCounts()
            }
        }
    }
    
    func decrementArticleCount() {
        if articleCount > 0 {
            articleCount -= 1
        }
    }
    
    func decrementPodcastCount() {
        if podcastCount > 0 {
            podcastCount -= 1
        }
    }

    func decrementNewsCount() {
        if newsCount > 0 {
            newsCount -= 1
        }
    }
    
    func incrementArticleCount() {
        articleCount += 1
    }
    
    func incrementPodcastCount() {
        podcastCount += 1
    }

    func incrementNewsCount() {
        newsCount += 1
    }
}
