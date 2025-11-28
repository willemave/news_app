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

    var defaultModel: String {
        switch self {
        case .openai:
            return "gpt-5.1"
        case .anthropic:
            return "claude-3-5-sonnet-latest"
        case .google:
            return "gemini-2.5-flash"
        }
    }
}
