import Foundation

enum SpeechTranscriptionState: Equatable {
    case idle
    case recording
    case transcribing
}

@MainActor
protocol SpeechTranscribing: AnyObject {
    var onTranscriptDelta: ((String) -> Void)? { get set }
    var onTranscriptFinal: ((String) -> Void)? { get set }
    var onError: ((String) -> Void)? { get set }
    var onStateChange: ((SpeechTranscriptionState) -> Void)? { get set }

    var isRecording: Bool { get }
    var isTranscribing: Bool { get }

    func start() async throws
    func stop() async throws -> String
    func cancel()
    func reset()
}
