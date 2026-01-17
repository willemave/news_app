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
}
