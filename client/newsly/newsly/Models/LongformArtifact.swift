//
//  LongformArtifact.swift
//  newsly
//
//  Typed long-form artifact models.
//

import Foundation

struct LongformFeedPreview: Codable, Equatable {
    let title: String
    let oneLine: String
    let previewBullets: [String]
    let reasonToRead: String
    let artifactType: String

    enum CodingKeys: String, CodingKey {
        case title
        case oneLine = "one_line"
        case previewBullets = "preview_bullets"
        case reasonToRead = "reason_to_read"
        case artifactType = "artifact_type"
    }
}

struct LongformSelectionTrace: Codable {
    let sourceHint: String
    let candidates: [String]
    let selected: String
    let reason: String
    let confidence: Double

    enum CodingKeys: String, CodingKey {
        case sourceHint = "source_hint"
        case candidates
        case selected
        case reason
        case confidence
    }
}

struct LongformSourceContext: Codable {
    let url: String
    let sourceName: String?
    let publicationDate: String?
    let platform: String?

    enum CodingKeys: String, CodingKey {
        case url
        case sourceName = "source_name"
        case publicationDate = "publication_date"
        case platform
    }
}

struct LongformArtifactQuote: Codable, Identifiable {
    let text: String
    let attribution: String?

    var id: String { text }
}

struct LongformArtifactKeyPoint: Codable, Identifiable {
    let heading: String
    let content: String

    var id: String { heading + String(content.prefix(20)) }
}

struct LongformArtifactPayload: Codable {
    let overview: String
    let quotes: [LongformArtifactQuote]
    let extrasRaw: [String: AnyCodable]
    let keyPoints: [LongformArtifactKeyPoint]
    let takeaway: String

    enum CodingKeys: String, CodingKey {
        case overview
        case quotes
        case extrasRaw = "extras"
        case keyPoints = "key_points"
        case takeaway
    }

    var extrasSections: [LongformExtrasSection] {
        extrasRaw.compactMap { key, value in
            LongformExtrasSection.make(title: key, rawValue: value.value)
        }
        .sorted { $0.title < $1.title }
    }
}

struct LongformArtifactBody: Codable {
    let type: String
    let payload: LongformArtifactPayload
}

struct LongformArtifactEnvelope: Codable {
    let title: String
    let oneLine: String
    let ask: String
    let artifact: LongformArtifactBody
    let generatedAt: String?
    let sourceContext: LongformSourceContext?
    let selectionTrace: LongformSelectionTrace?
    let feedPreview: LongformFeedPreview?

    enum CodingKeys: String, CodingKey {
        case title
        case oneLine = "one_line"
        case ask
        case artifact
        case generatedAt = "generated_at"
        case sourceContext = "source_context"
        case selectionTrace = "selection_trace"
        case feedPreview = "feed_preview"
    }

    var displayType: String {
        switch artifact.type {
        case "argument": return "Argument"
        case "mental_model": return "Mental Model"
        case "playbook": return "Playbook"
        case "portrait": return "Portrait"
        case "briefing": return "Briefing"
        case "walkthrough": return "Walkthrough"
        case "findings": return "Findings"
        default: return artifact.type.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }
}

struct LongformExtrasSection: Identifiable {
    let title: String
    let items: [String]

    var id: String { title }

    static func make(title rawTitle: String, rawValue: Any) -> LongformExtrasSection? {
        let title = rawTitle
            .replacingOccurrences(of: "_", with: " ")
            .capitalized

        if let string = rawValue as? String {
            let trimmed = string.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? nil : LongformExtrasSection(title: title, items: [trimmed])
        }

        if let strings = rawValue as? [String] {
            let items = strings
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
            return items.isEmpty ? nil : LongformExtrasSection(title: title, items: items)
        }

        if let dictionaries = rawValue as? [[String: Any]] {
            let items = dictionaries.compactMap { dictionary in
                dictionary
                    .sorted { $0.key < $1.key }
                    .compactMap { key, value -> String? in
                        let text = "\(value)".trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !text.isEmpty, text != "<null>" else { return nil }
                        let label = key.replacingOccurrences(of: "_", with: " ").capitalized
                        return "\(label): \(text)"
                    }
                    .joined(separator: " · ")
            }
            .filter { !$0.isEmpty }
            return items.isEmpty ? nil : LongformExtrasSection(title: title, items: items)
        }

        return nil
    }
}
