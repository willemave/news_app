//
//  OnboardingService.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import Foundation

final class OnboardingService {
    static let shared = OnboardingService()
    private let client = APIClient.shared

    private init() {}

    func buildProfile(request: OnboardingProfileRequest) async throws -> OnboardingProfileResponse {
        let body = try JSONEncoder().encode(request)
        return try await client.request(
            APIEndpoints.onboardingProfile,
            method: "POST",
            body: body
        )
    }

    func fastDiscover(request: OnboardingFastDiscoverRequest) async throws -> OnboardingFastDiscoverResponse {
        let body = try JSONEncoder().encode(request)
        return try await client.request(
            APIEndpoints.onboardingFastDiscover,
            method: "POST",
            body: body
        )
    }

    func complete(request: OnboardingCompleteRequest) async throws -> OnboardingCompleteResponse {
        let body = try JSONEncoder().encode(request)
        return try await client.request(
            APIEndpoints.onboardingComplete,
            method: "POST",
            body: body
        )
    }

    func markTutorialComplete() async throws -> OnboardingTutorialResponse {
        try await client.request(
            APIEndpoints.onboardingTutorialComplete,
            method: "POST"
        )
    }
}
