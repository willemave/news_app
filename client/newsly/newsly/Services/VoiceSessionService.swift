//
//  VoiceSessionService.swift
//  newsly
//

import Foundation
import os.log

enum VoiceSessionServiceError: LocalizedError {
    case missingAccessToken
    case invalidWebSocketURL

    var errorDescription: String? {
        switch self {
        case .missingAccessToken:
            return "You must be signed in to start Live Voice."
        case .invalidWebSocketURL:
            return "Invalid voice websocket URL."
        }
    }
}

final class VoiceSessionService {
    static let shared = VoiceSessionService()

    private let client = APIClient.shared
    private let logger = Logger(subsystem: "com.newsly", category: "VoiceSessionService")

    private init() {}

    func createSession(_ request: VoiceCreateSessionRequest) async throws -> VoiceCreateSessionResponse {
        logger.info(
            "Creating voice session | mode=\(request.launchMode.rawValue, privacy: .public) source=\(request.sourceSurface.rawValue, privacy: .public) contentId=\(request.contentId ?? -1) chatSessionId=\(request.chatSessionId ?? -1)"
        )
        let body = try JSONEncoder().encode(request)
        return try await client.request(
            APIEndpoints.voiceSessions,
            method: "POST",
            body: body
        )
    }

    func resolveWebSocketURL(path: String) throws -> URL {
        let baseURL = AppSettings.shared.baseURL
        guard let httpURL = URL(string: baseURL + path),
              var components = URLComponents(url: httpURL, resolvingAgainstBaseURL: false) else {
            logger.error("Failed to resolve websocket URL from baseURL/path")
            throw VoiceSessionServiceError.invalidWebSocketURL
        }
        components.scheme = AppSettings.shared.useHTTPS ? "wss" : "ws"
        guard let wsURL = components.url else {
            logger.error("Failed to build websocket URL from components")
            throw VoiceSessionServiceError.invalidWebSocketURL
        }
        logger.info("Resolved voice websocket URL: \(wsURL.absoluteString, privacy: .public)")
        return wsURL
    }

    func fetchAccessToken() async throws -> String {
        if let existing = KeychainManager.shared.getToken(key: .accessToken), !existing.isEmpty {
            return existing
        }

        let refreshed = try await AuthenticationService.shared.refreshAccessToken()
        guard !refreshed.isEmpty else {
            throw VoiceSessionServiceError.missingAccessToken
        }
        return refreshed
    }
}
