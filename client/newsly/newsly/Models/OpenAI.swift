import Foundation

struct RealtimeTokenResponse: Codable {
    let token: String
    let expiresAt: Int?
    let model: String?
    let sessionType: String?

    enum CodingKeys: String, CodingKey {
        case token
        case expiresAt = "expires_at"
        case model
        case sessionType = "session_type"
    }
}
