//
//  User.swift
//  newsly
//
//  Created by Assistant on 10/25/25.
//

import Foundation

/// User account model matching backend UserResponse schema
struct User: Codable, Identifiable, Equatable {
    let id: Int
    let appleId: String
    let email: String
    let fullName: String?
    let isAdmin: Bool
    let isActive: Bool
    let createdAt: Date
    let updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case appleId = "apple_id"
        case email
        case fullName = "full_name"
        case isAdmin = "is_admin"
        case isActive = "is_active"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

/// Token response from authentication endpoints
struct TokenResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let user: User
    let openaiApiKey: String?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case user
        case openaiApiKey = "openai_api_key"
    }
}

/// Request for token refresh
struct RefreshTokenRequest: Codable {
    let refreshToken: String

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
    }
}

/// Response for token refresh (with token rotation)
struct AccessTokenResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let openaiApiKey: String?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case openaiApiKey = "openai_api_key"
    }
}
