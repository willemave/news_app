import Foundation
import XCTest
@testable import newsly

final class UserProfileCodingTests: XCTestCase {
    func testUserDecodesNewsListPreferencePrompt() throws {
        let json = """
        {
          "id": 1,
          "apple_id": "apple-1",
          "email": "user@example.com",
          "full_name": "Test User",
          "twitter_username": "willem_aw",
          "news_list_preference_prompt": "Prefer semiconductors and infra updates.",
          "council_personas": [
            {
              "id": "analyst",
              "display_name": "Analyst",
              "instruction_prompt": "Focus on the core argument.",
              "sort_order": 0
            },
            {
              "id": "skeptic",
              "display_name": "Skeptic",
              "instruction_prompt": "Stress-test assumptions.",
              "sort_order": 1
            },
            {
              "id": "builder",
              "display_name": "Builder",
              "instruction_prompt": "Make it practical.",
              "sort_order": 2
            },
            {
              "id": "historian",
              "display_name": "Historian",
              "instruction_prompt": "Add historical context.",
              "sort_order": 3
            }
          ],
          "has_x_bookmark_sync": true,
          "is_admin": false,
          "is_active": true,
          "has_completed_onboarding": true,
          "has_completed_new_user_tutorial": true,
          "created_at": "2026-03-26T20:00:00Z",
          "updated_at": "2026-03-26T20:00:00Z"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let user = try decoder.decode(User.self, from: json)

        XCTAssertEqual(user.newsListPreferencePrompt, "Prefer semiconductors and infra updates.")
        XCTAssertEqual(user.councilPersonas.map(\.displayName), ["Analyst", "Skeptic", "Builder", "Historian"])
    }

    func testUpdateUserProfileRequestEncodesNewsListPreferencePrompt() throws {
        let request = UpdateUserProfileRequest(
            fullName: nil,
            twitterUsername: "willem_aw",
            newsListPreferencePrompt: "Keep market structure and product updates.",
            councilPersonas: [
                CouncilPersona(
                    id: "einstein",
                    displayName: "Albert Einstein",
                    instructionPrompt: "Reduce the issue to first principles.",
                    sortOrder: 0
                )
            ]
        )

        let data = try JSONEncoder().encode(request)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(
            json["news_list_preference_prompt"] as? String,
            "Keep market structure and product updates."
        )
        let councilPersonas = try XCTUnwrap(json["council_personas"] as? [[String: Any]])
        XCTAssertEqual(councilPersonas.first?["display_name"] as? String, "Albert Einstein")
    }

    func testOnboardingCompleteRequestEncodesNewsListPreferencePrompt() throws {
        let request = OnboardingCompleteRequest(
            selectedSources: [],
            selectedSubreddits: [],
            profileSummary: nil,
            inferredTopics: nil,
            twitterUsername: nil,
            newsListPreferencePrompt: "Prefer original reporting and firsthand product notes."
        )

        let data = try JSONEncoder().encode(request)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(
            json["news_list_preference_prompt"] as? String,
            "Prefer original reporting and firsthand product notes."
        )
    }

    func testUserFallsBackToDefaultCouncilPersonasWhenMissingFromPayload() throws {
        let json = """
        {
          "id": 1,
          "apple_id": "apple-1",
          "email": "user@example.com",
          "full_name": "Test User",
          "twitter_username": null,
          "news_list_preference_prompt": "",
          "has_x_bookmark_sync": false,
          "is_admin": false,
          "is_active": true,
          "has_completed_onboarding": true,
          "has_completed_new_user_tutorial": true,
          "created_at": "2026-03-26T20:00:00Z",
          "updated_at": "2026-03-26T20:00:00Z"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let user = try decoder.decode(User.self, from: json)

        XCTAssertEqual(user.councilPersonas, CouncilPersona.defaults)
    }
}
