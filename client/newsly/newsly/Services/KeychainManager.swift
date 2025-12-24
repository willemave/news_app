//
//  KeychainManager.swift
//  newsly
//
//  Created by Assistant on 10/25/25.
//

import Combine
import Foundation
import Security

/// Manages secure storage of authentication tokens in the iOS Keychain
final class KeychainManager {
    static let shared = KeychainManager()

    private init() {}

    private let serviceName = "com.newsly.app"
    private var accessGroup: String?

    enum KeychainKey: String {
        case accessToken = "accessToken"
        case refreshToken = "refreshToken"
        case userId = "userId"
        case openaiApiKey = "openaiApiKey"
    }

    /// Optional configuration for shared keychain access (e.g., extensions).
    func configure(accessGroup: String?) {
        self.accessGroup = accessGroup
    }

    /// Save a token to the keychain
    func saveToken(_ token: String, key: KeychainKey) {
        guard let data = token.data(using: .utf8) else { return }

        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key.rawValue,
            kSecValueData as String: data,
            // Allow background refreshes after first unlock so timers/URLSession tasks can read tokens
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]

        if let accessGroup {
            query[kSecAttrAccessGroup as String] = accessGroup
        }

        // Delete existing item if any
        SecItemDelete(query as CFDictionary)

        // Add new item
        let status = SecItemAdd(query as CFDictionary, nil)

        if status != errSecSuccess {
            print("Keychain save error: \(status)")
        }
    }

    /// Retrieve a token from the keychain
    func getToken(key: KeychainKey) -> String? {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        if let accessGroup {
            query[kSecAttrAccessGroup as String] = accessGroup
        }

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else {
            return nil
        }

        return token
    }

    /// Delete a specific token from the keychain
    func deleteToken(key: KeychainKey) {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key.rawValue
        ]

        if let accessGroup {
            query[kSecAttrAccessGroup as String] = accessGroup
        }

        SecItemDelete(query as CFDictionary)
    }

    /// Clear all authentication data from the keychain
    func clearAll() {
        deleteToken(key: .accessToken)
        deleteToken(key: .refreshToken)
        deleteToken(key: .userId)
        deleteToken(key: .openaiApiKey)
    }
}
