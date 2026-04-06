//
//  OnboardingE2EFixtureStore.swift
//  newsly
//
//  Created by Assistant on 4/4/26.
//

import Foundation

struct OnboardingE2EFixture: Decodable {
    let transcript: String?
    let audioDiscoverResponse: OnboardingAudioDiscoverResponse?
    let discoveryStatusResponse: OnboardingDiscoveryStatusResponse?

    enum CodingKeys: String, CodingKey {
        case transcript
        case audioDiscoverResponse = "audio_discover_response"
        case discoveryStatusResponse = "discovery_status_response"
    }
}

enum OnboardingE2EFixtureStore {
    static let shared: OnboardingE2EFixture? = loadFixture()

    private static func loadFixture() -> OnboardingE2EFixture? {
        guard let encodedFixture = E2ETestLaunch.onboardingFixture,
              let data = Data(base64Encoded: encodedFixture, options: [.ignoreUnknownCharacters]) else {
            return nil
        }

        let decoder = JSONDecoder()
        return try? decoder.decode(OnboardingE2EFixture.self, from: data)
    }
}
