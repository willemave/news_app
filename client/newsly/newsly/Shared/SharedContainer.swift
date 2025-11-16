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
    /// Set this to match your provisioning profile (must match entitlements).
    static let keychainAccessGroup: String? = "com.newsly.shared-keychain"

    static var userDefaults: UserDefaults {
        if let appGroupId, let defaults = UserDefaults(suiteName: appGroupId) {
            return defaults
        }
        return .standard
    }
}
