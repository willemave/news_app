//
//  OnboardingStateStore.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import Foundation

final class OnboardingStateStore {
    static let shared = OnboardingStateStore()

    private let pendingKey = "onboarding_pending_user_ids"
    private let discoveryRunKey = "onboarding_discovery_runs"
    private let defaults: UserDefaults

    private init() {
        defaults = SharedContainer.userDefaults
    }

    func setPending(userId: Int) {
        guard userId > 0 else { return }
        var ids = loadIds()
        ids.insert(userId)
        saveIds(ids)
    }

    func clearPending(userId: Int) {
        guard userId > 0 else { return }
        var ids = loadIds()
        ids.remove(userId)
        saveIds(ids)
    }

    func needsOnboarding(userId: Int) -> Bool {
        guard userId > 0 else { return false }
        return loadIds().contains(userId)
    }

    func setDiscoveryRun(userId: Int, runId: Int) {
        guard userId > 0, runId > 0 else { return }
        var runs = loadRunMap()
        runs[String(userId)] = runId
        saveRunMap(runs)
    }

    func discoveryRunId(userId: Int) -> Int? {
        guard userId > 0 else { return nil }
        return loadRunMap()[String(userId)]
    }

    func clearDiscoveryRun(userId: Int) {
        guard userId > 0 else { return }
        var runs = loadRunMap()
        runs.removeValue(forKey: String(userId))
        saveRunMap(runs)
    }

    private func loadIds() -> Set<Int> {
        guard let data = defaults.data(forKey: pendingKey) else { return [] }
        let decoded = (try? JSONDecoder().decode([Int].self, from: data)) ?? []
        return Set(decoded)
    }

    private func saveIds(_ ids: Set<Int>) {
        let payload = Array(ids)
        if let data = try? JSONEncoder().encode(payload) {
            defaults.set(data, forKey: pendingKey)
        }
    }

    private func loadRunMap() -> [String: Int] {
        guard let data = defaults.data(forKey: discoveryRunKey) else { return [:] }
        return (try? JSONDecoder().decode([String: Int].self, from: data)) ?? [:]
    }

    private func saveRunMap(_ runs: [String: Int]) {
        if let data = try? JSONEncoder().encode(runs) {
            defaults.set(data, forKey: discoveryRunKey)
        }
    }
}
