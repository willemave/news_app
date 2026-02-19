//
//  VoiceLive.swift
//  newsly
//

import Foundation

struct VoiceCreateSessionRequest: Codable {
    let sessionId: String?
    let sampleRateHz: Int
    let contentId: Int?
    let chatSessionId: Int?
    let launchMode: LiveLaunchMode
    let sourceSurface: LiveVoiceSourceSurface
    let requestIntro: Bool

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case sampleRateHz = "sample_rate_hz"
        case contentId = "content_id"
        case chatSessionId = "chat_session_id"
        case launchMode = "launch_mode"
        case sourceSurface = "source_surface"
        case requestIntro = "request_intro"
    }
}

struct VoiceCreateSessionResponse: Codable {
    let sessionId: String
    let websocketPath: String
    let sampleRateHz: Int
    let channels: Int
    let audioFormat: String
    let ttsOutputFormat: String
    let maxInputSeconds: Int
    let chatSessionId: Int
    let launchMode: LiveLaunchMode
    let contentContextAttached: Bool

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case websocketPath = "websocket_path"
        case sampleRateHz = "sample_rate_hz"
        case channels
        case audioFormat = "audio_format"
        case ttsOutputFormat = "tts_output_format"
        case maxInputSeconds = "max_input_seconds"
        case chatSessionId = "chat_session_id"
        case launchMode = "launch_mode"
        case contentContextAttached = "content_context_attached"
    }
}

struct VoiceServerEvent: Codable {
    let type: String
    let sessionId: String?
    let userId: Int?
    let chatSessionId: Int?
    let launchMode: LiveLaunchMode?
    let turnId: String?
    let text: String?
    let seq: Int?
    let audioB64: String?
    let format: String?
    let code: String?
    let message: String?
    let retryable: Bool?
    let latencyMs: Int?
    let ttsEnabled: Bool?
    let reason: String?
    let isIntro: Bool?
    let isOnboardingIntro: Bool?

    enum CodingKeys: String, CodingKey {
        case type
        case sessionId = "session_id"
        case userId = "user_id"
        case chatSessionId = "chat_session_id"
        case launchMode = "launch_mode"
        case turnId = "turn_id"
        case text
        case seq
        case audioB64 = "audio_b64"
        case format
        case code
        case message
        case retryable
        case latencyMs = "latency_ms"
        case ttsEnabled = "tts_enabled"
        case reason
        case isIntro = "is_intro"
        case isOnboardingIntro = "is_onboarding_intro"
    }
}
