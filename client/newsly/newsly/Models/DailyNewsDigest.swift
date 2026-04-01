//
//  DailyNewsDigest.swift
//  newsly
//

import Foundation

struct DailyNewsDigestCitation: Codable, Identifiable, Equatable {
    let newsItemId: Int
    let label: String?
    let title: String
    let url: String?
    let articleUrl: String?

    enum CodingKeys: String, CodingKey {
        case newsItemId = "news_item_id"
        case label
        case title
        case url
        case articleUrl = "article_url"
    }

    var effectiveURL: String? {
        url ?? articleUrl
    }

    private static let inlineSourceCharacterLimit = 9

    private static func trimmedValue(_ value: String?) -> String? {
        guard
            let value = value?.trimmingCharacters(in: .whitespacesAndNewlines),
            !value.isEmpty
        else {
            return nil
        }
        return value
    }

    private static func parsedURL(from rawURL: String?) -> URL? {
        guard let rawURL = trimmedValue(rawURL) else {
            return nil
        }
        return URL(string: rawURL)
    }

    private static func normalizedHost(from rawURL: String?) -> String? {
        guard let parsedURL = parsedURL(from: rawURL) else {
            return nil
        }
        guard var host = trimmedValue(parsedURL.host) else {
            return nil
        }
        if host.hasPrefix("www.") {
            host.removeFirst(4)
        }
        return host.isEmpty ? nil : host
    }

    private static func normalizedPathComponents(from rawURL: String?) -> [String] {
        guard let parsedURL = parsedURL(from: rawURL) else {
            return []
        }
        return parsedURL.pathComponents.filter { component in
            component != "/" && !component.isEmpty
        }
    }

    private static func mappedHostToken(_ host: String) -> String? {
        switch host.lowercased() {
        case "news.ycombinator.com":
            return "HN"
        case "techmeme.com":
            return "Techmeme"
        case "semianalysis.com":
            return "SemiAnal"
        case "theinformation.com":
            return "The Info"
        default:
            return nil
        }
    }

    private static func redditToken(from rawURL: String?) -> String? {
        guard let host = normalizedHost(from: rawURL) else {
            return nil
        }
        guard host == "reddit.com" || host == "redd.it" else {
            return nil
        }
        let components = normalizedPathComponents(from: rawURL)
        guard let redditIndex = components.firstIndex(where: { $0.lowercased() == "r" }) else {
            return "Reddit"
        }
        let subredditIndex = redditIndex + 1
        guard subredditIndex < components.count else {
            return "Reddit"
        }
        guard let subreddit = trimmedValue(components[subredditIndex]) else {
            return "Reddit"
        }
        return "r/\(subreddit)"
    }

    private static func socialUsernameToken(from rawURL: String?) -> String? {
        guard let host = normalizedHost(from: rawURL) else {
            return nil
        }
        guard host == "x.com" || host == "twitter.com" else {
            return nil
        }
        let components = normalizedPathComponents(from: rawURL)
        guard let firstComponent = components.first else {
            return "X"
        }
        let reservedComponents = Set([
            "explore", "hashtag", "home", "i", "intent", "messages", "search", "settings", "share"
        ])
        let username = firstComponent.trimmingCharacters(in: CharacterSet(charactersIn: "@"))
        guard !reservedComponents.contains(username.lowercased()), !username.isEmpty else {
            return "X"
        }
        return "@\(username)"
    }

    private static func preferredLabelToken(_ label: String?) -> String? {
        guard let label = trimmedValue(label) else {
            return nil
        }
        switch label.lowercased() {
        case "hacker news":
            return "HN"
        case "twitter", "x":
            return "X"
        default:
            return label
        }
    }

    var inlineSourceToken: String {
        let smartURLToken = [
            Self.redditToken(from: effectiveURL),
            Self.redditToken(from: articleUrl),
            Self.socialUsernameToken(from: effectiveURL),
            Self.socialUsernameToken(from: articleUrl)
        ]
        .compactMap { $0 }
        .first

        let candidates = [
            smartURLToken,
            Self.preferredLabelToken(label),
            Self.normalizedHost(from: effectiveURL).flatMap(Self.mappedHostToken) ?? Self.normalizedHost(from: effectiveURL),
            Self.normalizedHost(from: articleUrl).flatMap(Self.mappedHostToken) ?? Self.normalizedHost(from: articleUrl),
            Self.trimmedValue(title)
        ]
        let resolved = candidates
            .compactMap(Self.trimmedValue)
            .first { !$0.isEmpty }

        guard let resolved else {
            return ""
        }
        let truncated = String(resolved.prefix(Self.inlineSourceCharacterLimit))
        return truncated.trimmingCharacters(in: CharacterSet(charactersIn: " ./"))
    }

    var id: String {
        "\(newsItemId):\(effectiveURL ?? title)"
    }

    init(
        newsItemId: Int,
        label: String? = nil,
        title: String,
        url: String? = nil,
        articleUrl: String? = nil
    ) {
        self.newsItemId = newsItemId
        self.label = label
        self.title = title
        self.url = url
        self.articleUrl = articleUrl
    }
}

struct DailyNewsDigestBulletDetail: Codable, Identifiable, Equatable {
    let id: Int
    let position: Int
    let topic: String
    let details: String
    let sourceCount: Int
    let citations: [DailyNewsDigestCitation]
    let commentQuotes: [String]

    enum CodingKeys: String, CodingKey {
        case id
        case position
        case topic
        case details
        case sourceCount = "source_count"
        case citations
        case commentQuotes = "comment_quotes"
    }

    init(
        id: Int,
        position: Int,
        topic: String,
        details: String,
        sourceCount: Int,
        citations: [DailyNewsDigestCitation] = [],
        commentQuotes: [String] = []
    ) {
        self.id = id
        self.position = position
        self.topic = topic
        self.details = details
        self.sourceCount = sourceCount
        self.citations = citations
        self.commentQuotes = commentQuotes
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        position = try container.decode(Int.self, forKey: .position)
        topic = try container.decode(String.self, forKey: .topic)
        details = try container.decode(String.self, forKey: .details)
        sourceCount = try container.decode(Int.self, forKey: .sourceCount)
        citations = try container.decodeIfPresent([DailyNewsDigestCitation].self, forKey: .citations) ?? []
        commentQuotes = try container.decodeIfPresent([String].self, forKey: .commentQuotes) ?? []
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(position, forKey: .position)
        try container.encode(topic, forKey: .topic)
        try container.encode(details, forKey: .details)
        try container.encode(sourceCount, forKey: .sourceCount)
        try container.encode(citations, forKey: .citations)
        try container.encode(commentQuotes, forKey: .commentQuotes)
    }

    var text: String {
        details
    }

    var cleanedText: String {
        details.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var digestPreviewText: String {
        var preview = cleanedText
        for quote in cleanedCommentQuotes where !quote.isEmpty {
            let suffixes = [
                " \"\(quote)\"",
                " “\(quote)”",
                " '\(quote)'",
                " ‘\(quote)’",
                " \(quote)",
            ]
            for suffix in suffixes where preview.hasSuffix(suffix) {
                preview.removeLast(suffix.count)
                preview = preview.trimmingCharacters(in: .whitespacesAndNewlines)
                break
            }
        }
        return preview
    }

    var cleanedCommentQuotes: [String] {
        commentQuotes
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    var inlineSourceTokens: [String] {
        var seenTokens = Set<String>()
        var tokens: [String] = []

        for citation in citations {
            let token = citation.inlineSourceToken
            guard !token.isEmpty else {
                continue
            }
            guard !seenTokens.contains(token) else {
                continue
            }
            seenTokens.insert(token)
            tokens.append(token)
        }

        return tokens
    }

    var digestPreviewWithSources: String {
        let preview = digestPreviewText
        guard !preview.isEmpty else {
            return preview
        }
        guard !inlineSourceTokens.isEmpty else {
            return preview
        }
        return "\(preview) [\(inlineSourceTokens.joined(separator: ", "))]"
    }
}

struct DailyNewsDigest: Codable, Identifiable {
    let id: Int
    let timezone: String
    let title: String
    let summary: String
    let sourceCount: Int
    let groupCount: Int
    var isRead: Bool
    let readAt: String?
    let generatedAt: String
    let triggerReason: String
    let windowStartAt: String
    let windowEndAt: String
    let bullets: [DailyNewsDigestBulletDetail]

    enum CodingKeys: String, CodingKey {
        case id
        case timezone
        case title
        case summary
        case sourceCount = "source_count"
        case groupCount = "group_count"
        case isRead = "is_read"
        case readAt = "read_at"
        case generatedAt = "generated_at"
        case triggerReason = "trigger_reason"
        case windowStartAt = "window_start_at"
        case windowEndAt = "window_end_at"
        case bullets
    }

    init(
        id: Int,
        timezone: String,
        title: String,
        summary: String,
        sourceCount: Int,
        groupCount: Int,
        isRead: Bool,
        readAt: String? = nil,
        generatedAt: String,
        triggerReason: String,
        windowStartAt: String,
        windowEndAt: String,
        bullets: [DailyNewsDigestBulletDetail] = []
    ) {
        self.id = id
        self.timezone = timezone
        self.title = title
        self.summary = summary
        self.sourceCount = sourceCount
        self.groupCount = groupCount
        self.isRead = isRead
        self.readAt = readAt
        self.generatedAt = generatedAt
        self.triggerReason = triggerReason
        self.windowStartAt = windowStartAt
        self.windowEndAt = windowEndAt
        self.bullets = bullets
    }

    private static let isoDateParser: ISO8601DateFormatter = {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return parser
    }()

    private static let dayLabelFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMM d"
        return formatter
    }()

    private static let timeLabelFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        return formatter
    }()

    static func parseGeneratedAt(_ isoDate: String) -> Date? {
        parseDate(isoDate)
    }

    static private func parseDate(_ isoDate: String) -> Date? {
        let parser = isoDateParser
        if let date = parser.date(from: isoDate) {
            return date
        }
        parser.formatOptions = [.withInternetDateTime]
        return parser.date(from: isoDate)
    }

    private static let localDateParser: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    private static func formatDate(_ isoDate: String, timezoneName: String) -> String? {
        guard let parsedDate = parseDate(isoDate) else {
            return nil
        }
        let output = localDateParser
        output.timeZone = TimeZone(identifier: timezoneName) ?? TimeZone.current
        return output.string(from: parsedDate)
    }

    var localDate: String {
        Self.formatDate(windowStartAt, timezoneName: timezone) ?? ""
    }

    var localDateValue: Date? {
        Self.localDateParser.date(from: localDate)
    }

    var displayDateLabel: String {
        guard let date = localDateValue else { return localDate }
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            return "Today"
        }
        if calendar.isDateInYesterday(date) {
            return "Yesterday"
        }
        return Self.dayLabelFormatter.string(from: date)
    }

    var displayTimeLabel: String {
        guard let date = Self.parseDate(generatedAt) else {
            return ""
        }
        return Self.timeLabelFormatter.string(from: date)
    }

    var articleCountLabel: String {
        "\(sourceCount) \(sourceCount == 1 ? "article" : "articles")"
    }

    var cleanedSummary: String {
        summary.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var displayBulletDetails: [DailyNewsDigestBulletDetail] {
        bullets.filter { !$0.cleanedText.isEmpty }
    }

    var cleanedSourceLabels: [String] {
        var seenLabels = Set<String>()
        var labels: [String] = []

        for bullet in bullets {
            for citation in bullet.citations {
                guard let label = citation.label?.trimmingCharacters(in: .whitespacesAndNewlines) else {
                    continue
                }
                guard !label.isEmpty else {
                    continue
                }
                guard !seenLabels.contains(label) else {
                    continue
                }
                seenLabels.insert(label)
                labels.append(label)
            }
        }

        return labels
    }

    var showsDigDeeperAction: Bool {
        !displayBulletDetails.isEmpty
    }
}

struct DailyNewsDigestListResponse: Codable {
    let digests: [DailyNewsDigest]
    let meta: PaginationMetadata

    var nextCursor: String? { meta.nextCursor }
    var hasMore: Bool { meta.hasMore }
}
