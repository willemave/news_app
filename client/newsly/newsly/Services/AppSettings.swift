//
//  AppSettings.swift
//  newsly
//
//  Created by Assistant on 7/9/25.
//

import Combine
import Foundation
import SwiftUI
import os.log

private let appSettingsLogger = Logger(
    subsystem: Bundle.main.bundleIdentifier ?? "org.willemaw.newsly",
    category: "AppSettings"
)

enum ServerConfigurationDefaults {
    static let hostKey = "serverHost"
    static let portKey = "serverPort"
    static let useHTTPSKey = "useHTTPS"
    static let defaultHost = "localhost"
    static let defaultPort = "8000"

    static func applyDebugDefaultsIfNeeded(to userDefaults: UserDefaults) {
#if DEBUG
        let persistedHost = persistedString(forKey: hostKey, in: userDefaults)
        let persistedPort = persistedString(forKey: portKey, in: userDefaults)

        guard persistedHost == nil || persistedPort == nil else {
            return
        }

        if persistedHost == nil {
            userDefaults.set(defaultHost, forKey: hostKey)
        }

        if persistedPort == nil {
            userDefaults.set(defaultPort, forKey: portKey)
        }

        if userDefaults.object(forKey: useHTTPSKey) == nil {
            userDefaults.set(false, forKey: useHTTPSKey)
        }

        appSettingsLogger.notice(
            "Seeded debug server configuration host=\(persistedHost ?? defaultHost, privacy: .public) port=\(persistedPort ?? defaultPort, privacy: .public)"
        )
#endif
    }

    static func hasPersistedServerConfiguration(in userDefaults: UserDefaults) -> Bool {
        persistedString(forKey: hostKey, in: userDefaults) != nil
            && persistedString(forKey: portKey, in: userDefaults) != nil
    }

    private static func persistedString(forKey key: String, in userDefaults: UserDefaults) -> String? {
        guard let value = userDefaults.string(forKey: key)?
            .trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else {
            return nil
        }
        return value
    }
}

enum FastNewsMode: String, CaseIterable {
    case newsList = "news_list"
    case dailyDigest = "daily_digest"

    var title: String {
        switch self {
        case .newsList:
            return "News List"
        case .dailyDigest:
            return "Daily Roll-Up"
        }
    }
}

enum NewsDigestIntervalOption: Int, CaseIterable {
    case every3Hours = 3
    case every6Hours = 6
    case every12Hours = 12

    var title: String {
        switch self {
        case .every3Hours:
            return "3h"
        case .every6Hours:
            return "6h"
        case .every12Hours:
            return "12h"
        }
    }

    var detail: String {
        switch self {
        case .every3Hours:
            return "Every 3 hours"
        case .every6Hours:
            return "Every 6 hours"
        case .every12Hours:
            return "Every 12 hours"
        }
    }
}

enum LongArticleDisplayMode: String, CaseIterable {
    case narrative = "narrative"
    case keyPoints = "key_points"
    case both = "both"

    var title: String {
        switch self {
        case .narrative:
            return "Narrative"
        case .keyPoints:
            return "Key Points"
        case .both:
            return "Both"
        }
    }

    var detail: String {
        switch self {
        case .narrative:
            return "Show the narrative with notable quotes"
        case .keyPoints:
            return "Show key points with notable quotes"
        case .both:
            return "Show narrative, key points, and quotes"
        }
    }
}

class AppSettings: ObservableObject {
    static let shared = AppSettings()
    
    @AppStorage("serverHost", store: SharedContainer.userDefaults) var serverHost: String = "localhost"
    @AppStorage("serverPort", store: SharedContainer.userDefaults) var serverPort: String = "8000"
    @AppStorage("useHTTPS", store: SharedContainer.userDefaults) var useHTTPS: Bool = false
    @AppStorage("appTextSizeIndex", store: SharedContainer.userDefaults) var appTextSizeIndex: Int = 1
    @AppStorage("contentTextSizeIndex", store: SharedContainer.userDefaults) var contentTextSizeIndex: Int = 2
    @AppStorage("fastNewsMode", store: SharedContainer.userDefaults) var fastNewsMode: String = FastNewsMode.dailyDigest.rawValue
    @AppStorage("longArticleDisplayMode", store: SharedContainer.userDefaults) var longArticleDisplayMode: String = LongArticleDisplayMode.both.rawValue
    @AppStorage("useLongFormCardStack", store: SharedContainer.userDefaults) var useLongFormCardStack: Bool = true
    @AppStorage("backendTranscriptionAvailable", store: SharedContainer.userDefaults) var backendTranscriptionAvailable: Bool = false
    private var hasExplicitServerConfiguration: Bool {
        ServerConfigurationDefaults.hasPersistedServerConfiguration(in: SharedContainer.userDefaults)
    }
    private var normalizedHost: String {
#if targetEnvironment(simulator)
        if serverHost.caseInsensitiveCompare("localhost") == .orderedSame {
            return "127.0.0.1"
        }
#endif
        return serverHost
    }

    var baseURL: String {
        if !hasExplicitServerConfiguration {
            appSettingsLogger.fault("Using implicit default server configuration")
#if DEBUG
            preconditionFailure("Server host/port must be configured explicitly in debug builds")
#endif
        }
        let scheme = useHTTPS ? "https" : "http"
        return "\(scheme)://\(normalizedHost):\(serverPort)"
    }

    func setBackendTranscriptionAvailable(_ isAvailable: Bool) {
        backendTranscriptionAvailable = isAvailable
    }
    
    private init() {
        ServerConfigurationDefaults.applyDebugDefaultsIfNeeded(to: SharedContainer.userDefaults)
    }
}
