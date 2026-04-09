import XCTest
@testable import newsly

final class CLILinkServiceTests: XCTestCase {
    func testParseScannedCodeExtractsSessionAndApproveToken() throws {
        let payload = try CLILinkScanPayload.parse(
            from: "newsly://cli-link?session_id=session-123&approve_token=approve-456"
        )

        XCTAssertEqual(payload.sessionID, "session-123")
        XCTAssertEqual(payload.approveToken, "approve-456")
    }

    func testParseScannedCodeRejectsUnexpectedScheme() {
        XCTAssertThrowsError(
            try CLILinkScanPayload.parse(
                from: "https://example.com/cli-link?session_id=session-123&approve_token=approve-456"
            )
        )
    }

    func testParseURLExtractsSessionAndApproveToken() throws {
        let url = try XCTUnwrap(
            URL(string: "newsly://cli-link?session_id=session-789&approve_token=approve-abc")
        )

        let payload = try CLILinkScanPayload.parse(from: url)

        XCTAssertEqual(payload.sessionID, "session-789")
        XCTAssertEqual(payload.approveToken, "approve-abc")
    }

    func testCanHandleRecognizesCLILinkURL() throws {
        let url = try XCTUnwrap(
            URL(string: "newsly://cli-link?session_id=session-123&approve_token=approve-456")
        )

        XCTAssertTrue(CLILinkScanPayload.canHandle(url))
    }

    func testCanHandleRejectsOtherNewslyURLs() throws {
        let url = try XCTUnwrap(URL(string: "newsly://oauth?code=test"))

        XCTAssertFalse(CLILinkScanPayload.canHandle(url))
    }
}
