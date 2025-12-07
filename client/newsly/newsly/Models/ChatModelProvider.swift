//
//  ChatModelProvider.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import Foundation

/// Available LLM providers for chat sessions
enum ChatModelProvider: String, Codable, CaseIterable {
    case openai
    case anthropic
    case google

    var displayName: String {
        switch self {
        case .openai:
            return "GPT"
        case .anthropic:
            return "Claude"
        case .google:
            return "Gemini"
        }
    }

    /// SF Symbol icon name (used for menus that require system images)
    var iconName: String {
        switch self {
        case .openai:
            return "brain.head.profile"
        case .anthropic:
            return "sparkles"
        case .google:
            return "diamond"
        }
    }

    /// Custom asset icon name
    var iconAsset: String {
        switch self {
        case .openai:
            return "openai-icon"
        case .anthropic:
            return "claude-icon"
        case .google:
            return "gemini-icon"
        }
    }

    var defaultModel: String {
        switch self {
        case .openai:
            return "gpt-5.1"
        case .anthropic:
            return "claude-sonnet-4-5-20250929"
        case .google:
            return "gemini-3-pro-preview"
        }
    }
}
