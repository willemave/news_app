import Foundation

enum SpeechTranscriptionState: Equatable {
    case idle
    case recording
    case transcribing
}

enum SpeechStopReason: Equatable {
    case manual
    case silenceAutoStop
    case cancel
    case failure
}

@MainActor
protocol SpeechTranscribing: AnyObject {
    var onTranscriptDelta: ((String) -> Void)? { get set }
    var onTranscriptFinal: ((String) -> Void)? { get set }
    var onError: ((String) -> Void)? { get set }
    var onStateChange: ((SpeechTranscriptionState) -> Void)? { get set }
    var onStopReason: ((SpeechStopReason) -> Void)? { get set }

    var isAvailable: Bool { get }
    var isRecording: Bool { get }
    var isTranscribing: Bool { get }

    func start() async throws
    func stop() async throws -> String
    func cancel()
    func reset()
}

extension SpeechTranscribing {
    var isAvailable: Bool {
        let accessToken = KeychainManager.shared.getToken(key: .accessToken)
        let refreshToken = KeychainManager.shared.getToken(key: .refreshToken)
        let hasAuthToken = !(accessToken?.isEmpty ?? true) || !(refreshToken?.isEmpty ?? true)
        return hasAuthToken && AppSettings.shared.backendTranscriptionAvailable
    }
}
