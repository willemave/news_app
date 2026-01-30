//
//  Onboarding.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import Foundation

struct OnboardingProfileRequest: Codable {
    let firstName: String
    let interestTopics: [String]

    enum CodingKeys: String, CodingKey {
        case firstName = "first_name"
        case interestTopics = "interest_topics"
    }
}

struct OnboardingProfileResponse: Codable {
    let profileSummary: String
    let inferredTopics: [String]
    let candidateSources: [String]

    enum CodingKeys: String, CodingKey {
        case profileSummary = "profile_summary"
        case inferredTopics = "inferred_topics"
        case candidateSources = "candidate_sources"
    }
}

struct OnboardingVoiceParseRequest: Codable {
    let transcript: String
    let locale: String?
}

struct OnboardingVoiceParseResponse: Codable {
    let firstName: String?
    let interestTopics: [String]
    let confidence: Double?
    let missingFields: [String]

    enum CodingKeys: String, CodingKey {
        case firstName = "first_name"
        case interestTopics = "interest_topics"
        case confidence
        case missingFields = "missing_fields"
    }
}

struct OnboardingSuggestion: Codable, Hashable {
    let suggestionType: String
    let title: String?
    let siteURL: String?
    let feedURL: String?
    let subreddit: String?
    let rationale: String?
    let score: Double?
    let isDefault: Bool

    enum CodingKeys: String, CodingKey {
        case suggestionType = "suggestion_type"
        case title
        case siteURL = "site_url"
        case feedURL = "feed_url"
        case subreddit
        case rationale
        case score
        case isDefault = "is_default"
    }

    var stableKey: String {
        feedURL ?? subreddit ?? siteURL ?? title ?? UUID().uuidString
    }

    var displayTitle: String {
        if let title, !title.isEmpty {
            return title
        }
        if let subreddit, !subreddit.isEmpty {
            return "r/\(subreddit)"
        }
        return feedURL ?? "Untitled"
    }
}

struct OnboardingFastDiscoverRequest: Codable {
    let profileSummary: String
    let inferredTopics: [String]

    enum CodingKeys: String, CodingKey {
        case profileSummary = "profile_summary"
        case inferredTopics = "inferred_topics"
    }
}

struct OnboardingFastDiscoverResponse: Codable {
    let recommendedPods: [OnboardingSuggestion]
    let recommendedSubstacks: [OnboardingSuggestion]
    let recommendedSubreddits: [OnboardingSuggestion]

    enum CodingKeys: String, CodingKey {
        case recommendedPods = "recommended_pods"
        case recommendedSubstacks = "recommended_substacks"
        case recommendedSubreddits = "recommended_subreddits"
    }
}

struct OnboardingSelectedSource: Codable {
    let suggestionType: String
    let title: String?
    let feedURL: String
    let config: [String: String]?

    enum CodingKeys: String, CodingKey {
        case suggestionType = "suggestion_type"
        case title
        case feedURL = "feed_url"
        case config
    }
}

struct OnboardingCompleteRequest: Codable {
    let selectedSources: [OnboardingSelectedSource]
    let selectedSubreddits: [String]
    let profileSummary: String?
    let inferredTopics: [String]?

    enum CodingKeys: String, CodingKey {
        case selectedSources = "selected_sources"
        case selectedSubreddits = "selected_subreddits"
        case profileSummary = "profile_summary"
        case inferredTopics = "inferred_topics"
    }
}

struct OnboardingCompleteResponse: Codable {
    let status: String
    let taskId: Int?
    let inboxCountEstimate: Int
    let longformStatus: String
    let hasCompletedNewUserTutorial: Bool

    enum CodingKeys: String, CodingKey {
        case status
        case taskId = "task_id"
        case inboxCountEstimate = "inbox_count_estimate"
        case longformStatus = "longform_status"
        case hasCompletedNewUserTutorial = "has_completed_new_user_tutorial"
    }
}

struct OnboardingTutorialResponse: Codable {
    let hasCompletedNewUserTutorial: Bool

    enum CodingKeys: String, CodingKey {
        case hasCompletedNewUserTutorial = "has_completed_new_user_tutorial"
    }
}
