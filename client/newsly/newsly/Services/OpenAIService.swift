import Foundation

final class OpenAIService {
    static let shared = OpenAIService()
    private let client = APIClient.shared

    private init() {}

    func fetchRealtimeToken() async throws -> RealtimeTokenResponse {
        try await client.request(
            APIEndpoints.openaiRealtimeToken,
            method: "POST"
        )
    }
}
