//
//  DiscoveryViewModel.swift
//  newsly
//

import Foundation

@MainActor
class DiscoveryViewModel: ObservableObject {
    @Published var runs: [DiscoveryRunSuggestions] = []
    @Published var feeds: [DiscoverySuggestion] = []
    @Published var podcasts: [DiscoverySuggestion] = []
    @Published var youtube: [DiscoverySuggestion] = []
    @Published var runStatus: String?
    @Published var runCreatedAt: String?
    @Published var directionSummary: String?
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var podcastSearchQuery = ""
    @Published var podcastSearchResults: [DiscoveryPodcastSearchResult] = []
    @Published var isPodcastSearchLoading = false
    @Published var podcastSearchError: String?
    @Published var hasPodcastSearchRun = false

    private let service = DiscoveryService.shared
    private let contentService = ContentService.shared
    private var hasLoaded = false

    var hasSuggestions: Bool {
        if !runs.isEmpty {
            return runs.contains { run in
                !run.feeds.isEmpty || !run.podcasts.isEmpty || !run.youtube.isEmpty
            }
        }
        return !feeds.isEmpty || !podcasts.isEmpty || !youtube.isEmpty
    }

    var hasPodcastSearchResults: Bool {
        !podcastSearchResults.isEmpty
    }

    /// Whether a discovery job is currently running
    var isJobRunning: Bool {
        guard let status = runStatus else { return false }
        let runningStatuses = ["queued", "pending", "processing", "running"]
        return runningStatuses.contains(status.lowercased())
    }

    /// Human-readable description of the current job status
    var runStatusDescription: String {
        guard let status = runStatus else { return "Waiting to start" }
        switch status.lowercased() {
        case "queued":
            return "Queued for processing"
        case "pending":
            return "Waiting in queue"
        case "processing", "running":
            return "Analyzing your interests"
        case "completed":
            return "Completed"
        case "failed":
            return "Failed"
        default:
            return status.capitalized
        }
    }

    /// Current stage for the progress indicator (0-3)
    var currentJobStage: Int {
        guard let status = runStatus else { return 0 }
        switch status.lowercased() {
        case "queued":
            return 0
        case "pending":
            return 1
        case "processing", "running":
            return 2
        case "completed":
            return 4
        default:
            return 1
        }
    }

    func loadSuggestions(force: Bool = false) async {
        if hasLoaded && !force {
            return
        }
        isLoading = true
        errorMessage = nil
        do {
            let history = try await service.fetchHistory()
            apply(history)
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func refreshDiscovery() async {
        do {
            let response = try await service.refresh()
            // Update local state to show running indicator immediately
            runStatus = response.status
            ToastService.shared.showSuccess("Discovery queued")
        } catch {
            ToastService.shared.showError("Failed to refresh discovery: \(error.localizedDescription)")
        }
    }

    func subscribe(_ suggestion: DiscoverySuggestion) async {
        await subscribeSuggestions([suggestion.id])
    }

    func subscribeSuggestions(_ ids: [Int]) async {
        do {
            let response = try await service.subscribe(suggestionIds: ids)
            let processed = Set(response.subscribed + response.skipped)
            removeSuggestions(with: processed)
            if response.errors.isEmpty {
                ToastService.shared.showSuccess("Subscribed successfully")
            } else {
                ToastService.shared.showError("Some subscriptions failed")
            }
        } catch {
            ToastService.shared.showError("Failed to subscribe: \(error.localizedDescription)")
        }
    }

    func addItem(from suggestion: DiscoverySuggestion) async {
        guard suggestion.itemURL != nil else { return }
        do {
            let response = try await service.addItems(suggestionIds: [suggestion.id])
            if !response.created.isEmpty {
                ToastService.shared.showSuccess("Added item to inbox")
            } else {
                ToastService.shared.show("Item already exists", type: .info)
            }
        } catch {
            ToastService.shared.showError("Failed to add item: \(error.localizedDescription)")
        }
    }

    func dismiss(_ suggestion: DiscoverySuggestion) async {
        await dismissSuggestions([suggestion.id])
    }

    func dismissSuggestions(_ ids: [Int]) async {
        do {
            let response = try await service.dismiss(suggestionIds: ids)
            removeSuggestions(with: Set(response.dismissed))
        } catch {
            ToastService.shared.showError("Failed to dismiss suggestions: \(error.localizedDescription)")
        }
    }

    func clearAll() async {
        do {
            _ = try await service.clear()
            feeds = []
            podcasts = []
            youtube = []
            ToastService.shared.show("Discovery cleared", type: .info)
        } catch {
            ToastService.shared.showError("Failed to clear suggestions: \(error.localizedDescription)")
        }
    }

    func clearPodcastSearch() {
        podcastSearchQuery = ""
        podcastSearchResults = []
        podcastSearchError = nil
        hasPodcastSearchRun = false
    }

    func searchPodcastEpisodes(limit: Int = 10) async {
        let trimmed = podcastSearchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.count >= 2 else {
            podcastSearchResults = []
            podcastSearchError = nil
            hasPodcastSearchRun = false
            return
        }

        isPodcastSearchLoading = true
        podcastSearchError = nil
        hasPodcastSearchRun = true
        do {
            let response = try await service.searchPodcastEpisodes(query: trimmed, limit: limit)
            podcastSearchResults = response.results
        } catch {
            podcastSearchResults = []
            podcastSearchError = error.localizedDescription
        }
        isPodcastSearchLoading = false
    }

    func retryPodcastSearch() async {
        await searchPodcastEpisodes()
    }

    func addPodcastEpisode(_ result: DiscoveryPodcastSearchResult) async {
        guard let url = URL(string: result.episodeURL) else {
            ToastService.shared.showError("Invalid episode URL")
            return
        }

        do {
            let response = try await contentService.submitContent(url: url, title: result.title)
            if response.alreadyExists {
                ToastService.shared.show("Episode already added", type: .info)
            } else {
                ToastService.shared.showSuccess("Episode added to inbox")
            }
        } catch {
            ToastService.shared.showError("Failed to add episode: \(error.localizedDescription)")
        }
    }

    private func apply(_ response: DiscoverySuggestionsResponse) {
        runs = []
        feeds = response.feeds
        podcasts = response.podcasts
        youtube = response.youtube
        runStatus = response.runStatus
        runCreatedAt = response.runCreatedAt
        directionSummary = response.directionSummary
    }

    private func apply(_ response: DiscoveryHistoryResponse) {
        runs = response.runs
        if let latest = response.runs.first {
            feeds = latest.feeds
            podcasts = latest.podcasts
            youtube = latest.youtube
            runStatus = latest.runStatus
            runCreatedAt = latest.runCreatedAt
            directionSummary = latest.directionSummary
        } else {
            feeds = []
            podcasts = []
            youtube = []
            runStatus = nil
            runCreatedAt = nil
            directionSummary = nil
        }
    }

    private func removeSuggestions(with ids: Set<Int>) {
        guard !ids.isEmpty else { return }
        feeds.removeAll { ids.contains($0.id) }
        podcasts.removeAll { ids.contains($0.id) }
        youtube.removeAll { ids.contains($0.id) }
    }
}
