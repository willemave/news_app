import Foundation
import XCTest
@testable import newsly

@MainActor
final class ChatSessionViewModelTests: XCTestCase {
    func testDefaultChatDictationUsesRecordThenTranscribeService() {
        let viewModel = ChatSessionViewModel(sessionId: 42)
        let mirror = Mirror(reflecting: viewModel)
        let service = mirror.children.first { $0.label == "transcriptionService" }?.value as AnyObject?

        XCTAssertTrue(service === VoiceDictationService.shared)
    }

    func testStopVoiceRecordingPopulatesInputWithoutStreamingPreview() async {
        let transcriptionService = MockChatSpeechTranscriber(transcript: "Final transcript")
        let viewModel = ChatSessionViewModel(
            sessionId: 42,
            transcriptionService: transcriptionService
        )

        viewModel.isRecording = true
        XCTAssertEqual(viewModel.inputText, "")

        await viewModel.stopVoiceRecording()

        XCTAssertEqual(viewModel.inputText, "Final transcript")
        XCTAssertFalse(viewModel.isRecording)
        XCTAssertFalse(viewModel.isTranscribing)
        XCTAssertTrue(viewModel.messages.isEmpty)
    }

    func testStopVoiceRecordingAppendsToExistingDraft() async {
        let transcriptionService = MockChatSpeechTranscriber(transcript: "second thought")
        let viewModel = ChatSessionViewModel(
            sessionId: 42,
            transcriptionService: transcriptionService
        )

        viewModel.inputText = "First draft"
        viewModel.isRecording = true

        await viewModel.stopVoiceRecording()

        XCTAssertEqual(viewModel.inputText, "First draft second thought")
    }
}

@MainActor
private final class MockChatSpeechTranscriber: SpeechTranscribing {
    var onTranscriptDelta: ((String) -> Void)?
    var onTranscriptFinal: ((String) -> Void)?
    var onError: ((String) -> Void)?
    var onStateChange: ((SpeechTranscriptionState) -> Void)?
    var onStopReason: ((SpeechStopReason) -> Void)?

    var isAvailable = true
    var isRecording = false
    var isTranscribing = false

    private let transcript: String

    init(transcript: String) {
        self.transcript = transcript
    }

    func start() async throws {
        isRecording = true
        onStateChange?(.recording)
    }

    func stop() async throws -> String {
        isRecording = false
        isTranscribing = false
        onStateChange?(.idle)
        return transcript
    }

    func cancel() {
        reset()
        onStopReason?(.cancel)
    }

    func reset() {
        isRecording = false
        isTranscribing = false
        onStateChange?(.idle)
    }
}
