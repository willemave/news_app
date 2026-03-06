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

struct AudioTranscriptionResponse: Codable {
    let transcript: String
    let language: String?

    var text: String {
        transcript
    }

    enum CodingKeys: String, CodingKey {
        case transcript
        case text
        case language
    }

    init(transcript: String, language: String?) {
        self.transcript = transcript
        self.language = language
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        transcript =
            try container.decodeIfPresent(String.self, forKey: .transcript)
            ?? container.decode(String.self, forKey: .text)
        language = try container.decodeIfPresent(String.self, forKey: .language)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(transcript, forKey: .transcript)
        try container.encodeIfPresent(language, forKey: .language)
    }
}
