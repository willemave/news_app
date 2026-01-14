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

    private let service = DiscoveryService.shared
    private var hasLoaded = false

    var hasSuggestions: Bool {
        if !runs.isEmpty {
            return runs.contains { run in
                !run.feeds.isEmpty || !run.podcasts.isEmpty || !run.youtube.isEmpty
            }
        }
        return !feeds.isEmpty || !podcasts.isEmpty || !youtube.isEmpty
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
            ToastService.shared.showSuccess("Discovery queued (\(response.status))")
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
