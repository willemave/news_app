import Foundation

struct RealtimeTokenResponse: Codable {
    let token: String
    let expiresAt: Int?
    let model: String?

    enum CodingKeys: String, CodingKey {
        case token
        case expiresAt = "expires_at"
        case model
    }
}
