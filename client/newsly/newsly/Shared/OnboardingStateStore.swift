//
//  OnboardingStateStore.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import Foundation

final class OnboardingStateStore {
    static let shared = OnboardingStateStore()

    private let discoveryRunKey = "onboarding_discovery_runs"
    private let defaults: UserDefaults

    private init() {
        defaults = SharedContainer.userDefaults
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
