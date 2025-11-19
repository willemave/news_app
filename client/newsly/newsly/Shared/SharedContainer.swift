//
//  SharedContainer.swift
//  newsly
//
//  Created by Assistant on 11/19/25.
//

import Foundation

enum SharedContainer {
    /// App group identifier shared between the main app and extensions.
    /// Set this to your configured App Group (must match entitlements).
    static let appGroupId: String? = "group.com.newsly"

    /// Optional keychain access group shared between the main app and extensions.
    /// Set to nil to use the default keychain (works in simulator and device).
    /// If you need to share keychain between app and extensions, set this to:
    /// - On device: "$(TeamID).com.newsly.shared-keychain"
    /// - For now using nil to avoid simulator keychain errors (-34018)
    static let keychainAccessGroup: String? = nil

    static var userDefaults: UserDefaults {
        if let appGroupId, let defaults = UserDefaults(suiteName: appGroupId) {
            return defaults
        }
        return .standard
    }
}
