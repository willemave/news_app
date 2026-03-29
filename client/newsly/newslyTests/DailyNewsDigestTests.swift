//
//  DailyNewsDigestTests.swift
//  newslyTests
//

import XCTest
@testable import newsly

final class DailyNewsDigestTests: XCTestCase {
    func testCleanedSummaryTrimsWhitespace() {
        let digest = makeDigest(summary: "  Summary text.  ")

        XCTAssertEqual(digest.cleanedSummary, "Summary text.")
    }

    func testShowsDigDeeperActionWhenBulletsExist() {
        let digest = makeDigest(
            summary: "Summary text.",
            bullets: [
                DailyNewsDigestBulletDetail(
                    id: 1,
                    position: 1,
                    topic: "AI",
                    details: "First point",
                    sourceCount: 2
                )
            ]
        )

        XCTAssertTrue(digest.showsDigDeeperAction)
        XCTAssertEqual(digest.displayBulletDetails.map(\.cleanedText), ["First point"])
    }

    func testHidesDigDeeperActionWithoutBullets() {
        let digest = makeDigest(summary: "Summary text.")

        XCTAssertFalse(digest.showsDigDeeperAction)
        XCTAssertEqual(digest.displayBulletDetails, [])
    }

    func testDigestPreviewTextStripsTrailingCommentQuote() {
        let bullet = DailyNewsDigestBulletDetail(
            id: 1,
            position: 1,
            topic: "AI",
            details: "OpenAI shipped a new model. \"Biggest gain came from deleting work, not optimizing queries.\"",
            sourceCount: 2,
            commentQuotes: ["Biggest gain came from deleting work, not optimizing queries."]
        )

        XCTAssertEqual(
            bullet.digestPreviewText,
            "OpenAI shipped a new model."
        )
    }

    func testCleanedSourceLabelsDropsBlankEntriesAndDeduplicatesByLabel() {
        let digest = makeDigest(
            summary: "Summary text.",
            bullets: [
                DailyNewsDigestBulletDetail(
                    id: 1,
                    position: 1,
                    topic: "AI",
                    details: "First point",
                    sourceCount: 2,
                    citations: [
                        DailyNewsDigestCitation(
                            newsItemId: 11,
                            label: " @swyx ",
                            title: "Hacker News",
                            url: "https://news.ycombinator.com/item?id=1"
                        ),
                        DailyNewsDigestCitation(
                            newsItemId: 12,
                            label: "  ",
                            title: "Hacker News",
                            url: "https://news.ycombinator.com/item?id=2"
                        ),
                        DailyNewsDigestCitation(
                            newsItemId: 13,
                            label: "@swyx",
                            title: "Techmeme",
                            url: "https://www.techmeme.com"
                        ),
                        DailyNewsDigestCitation(
                            newsItemId: 14,
                            label: " OpenAI ",
                            title: "OpenAI",
                            url: "https://openai.com"
                        )
                    ]
                )
            ]
        )

        XCTAssertEqual(digest.cleanedSourceLabels, ["@swyx", "OpenAI"])
    }

    private func makeDigest(
        summary: String,
        bullets: [DailyNewsDigestBulletDetail] = []
    ) -> DailyNewsDigest {
        DailyNewsDigest(
            id: 7,
            timezone: "UTC",
            title: "Digest",
            summary: summary,
            sourceCount: 2,
            groupCount: bullets.count,
            isRead: false,
            generatedAt: "2026-03-08T18:00:00Z",
            triggerReason: "scheduler",
            windowStartAt: "2026-03-08T17:00:00Z",
            windowEndAt: "2026-03-08T18:00:00Z",
            bullets: bullets
        )
    }
}
