//
//  NarrationService.swift
//  newsly
//

import Foundation

final class NarrationService {
    static let shared = NarrationService()

    private let client = APIClient.shared

    private init() {}

    func fetchNarration(for target: NarrationTarget) async throws -> NarrationResponse {
        try await client.request(APIEndpoints.narration(target))
    }

    func fetchNarrationAudio(for target: NarrationTarget) async throws -> Data {
        try await client.requestData(
            APIEndpoints.narration(target),
            accept: "audio/mpeg"
        )
    }
}
