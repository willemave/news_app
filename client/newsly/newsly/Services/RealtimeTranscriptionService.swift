import AVFoundation
import Foundation
import os.log

private let realtimeLogger = Logger(subsystem: "com.newsly", category: "RealtimeTranscription")

enum RealtimeTranscriptionError: LocalizedError {
    case noMicrophoneAccess
    case audioSessionError(String)
    case connectionFailed
    case tokenMissing

    var errorDescription: String? {
        switch self {
        case .noMicrophoneAccess:
            return "Microphone access denied"
        case .audioSessionError(let message):
            return "Audio session error: \(message)"
        case .connectionFailed:
            return "Realtime connection failed"
        case .tokenMissing:
            return "Realtime token unavailable"
        }
    }
}

final class RealtimeTranscriptionService {
    var onTranscriptDelta: ((String) -> Void)?
    var onTranscriptFinal: ((String) -> Void)?
    var onError: ((String) -> Void)?
    var onStateChange: ((Bool) -> Void)?

    private let openAIService = OpenAIService.shared
    private let audioQueue = DispatchQueue(label: "com.newsly.realtime.audio")
    private let defaultModel = "gpt-realtime"
    private let transcriptionModel = "gpt-4o-mini-transcribe"
    private let targetSampleRate: Double = 24_000

    private var webSocket: URLSessionWebSocketTask?
    private var audioEngine: AVAudioEngine?
    private var audioConverter: AVAudioConverter?
    private var currentTranscript: String = ""
    private var isRecording = false

    func requestMicrophonePermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVAudioApplication.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
    }

    func start() async throws {
        guard !isRecording else { return }

        let hasPermission = await requestMicrophonePermission()
        guard hasPermission else {
            throw RealtimeTranscriptionError.noMicrophoneAccess
        }

        try configureAudioSession()
        let tokenResponse = try await openAIService.fetchRealtimeToken()
        let token = tokenResponse.token
        guard !token.isEmpty else {
            throw RealtimeTranscriptionError.tokenMissing
        }

        try await connect(token: token, model: tokenResponse.model)
        startAudioEngine()
        isRecording = true
        onStateChange?(true)
    }

    func stop() async -> String {
        guard isRecording else { return currentTranscript }
        stopAudioEngine()
        sendEvent(["type": "input_audio_buffer.commit"])
        sendEvent([
            "type": "response.create",
            "response": ["modalities": ["text"], "instructions": "Transcribe the audio."]
        ])
        try? await Task.sleep(nanoseconds: 400_000_000)
        webSocket?.cancel(with: .normalClosure, reason: nil)
        isRecording = false
        onStateChange?(false)
        return currentTranscript
    }

    func reset() {
        stopAudioEngine()
        webSocket?.cancel(with: .goingAway, reason: nil)
        currentTranscript = ""
        isRecording = false
    }

    // MARK: - Private

    private func configureAudioSession() throws {
        let audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker, .allowBluetooth])
            try audioSession.setPreferredSampleRate(targetSampleRate)
            try audioSession.setPreferredIOBufferDuration(0.02)
            try audioSession.setActive(true)
        } catch {
            throw RealtimeTranscriptionError.audioSessionError(error.localizedDescription)
        }
    }

    private func connect(token: String, model: String?) async throws {
        let modelValue = model ?? defaultModel
        guard var components = URLComponents(string: "wss://api.openai.com/v1/realtime") else {
            throw RealtimeTranscriptionError.connectionFailed
        }
        components.queryItems = [URLQueryItem(name: "model", value: modelValue)]
        guard let url = components.url else {
            throw RealtimeTranscriptionError.connectionFailed
        }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("realtime=v1", forHTTPHeaderField: "OpenAI-Beta")

        let task = URLSession.shared.webSocketTask(with: request)
        task.resume()
        webSocket = task
        listenForMessages()

        sendEvent([
            "type": "session.update",
            "session": [
                "input_audio_format": "pcm16",
                "input_audio_transcription": ["model": transcriptionModel],
                "turn_detection": ["type": "server_vad"]
            ]
        ])
    }

    private func listenForMessages() {
        webSocket?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error):
                realtimeLogger.error("WebSocket receive error: \(error.localizedDescription, privacy: .public)")
                self.onError?(error.localizedDescription)
            case .success(let message):
                self.handleMessage(message)
                self.listenForMessages()
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        let textPayload: String?
        switch message {
        case .string(let text):
            textPayload = text
        case .data(let data):
            textPayload = String(data: data, encoding: .utf8)
        @unknown default:
            textPayload = nil
        }

        guard let textPayload,
              let data = textPayload.data(using: .utf8),
              let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let type = json["type"] as? String else {
            return
        }

        if let errorPayload = json["error"] as? [String: Any],
           let message = errorPayload["message"] as? String {
            onError?(message)
            return
        }

        if type.hasSuffix(".delta"), let delta = json["delta"] as? String {
            currentTranscript += delta
            onTranscriptDelta?(delta)
            return
        }

        if let text = json["text"] as? String {
            currentTranscript = text
            onTranscriptFinal?(text)
            return
        }

        if let transcript = json["transcript"] as? String {
            currentTranscript = transcript
            onTranscriptFinal?(transcript)
        }
    }

    private func startAudioEngine() {
        let audioEngine = AVAudioEngine()
        let inputNode = audioEngine.inputNode
        let inputFormat = inputNode.outputFormat(forBus: 0)
        guard let targetFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: targetSampleRate, channels: 1, interleaved: true),
              let converter = AVAudioConverter(from: inputFormat, to: targetFormat) else {
            return
        }

        audioConverter = converter
        self.audioEngine = audioEngine

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: inputFormat) { [weak self] buffer, _ in
            self?.audioQueue.async {
                self?.sendAudioBuffer(buffer, targetFormat: targetFormat)
            }
        }

        do {
            try audioEngine.start()
        } catch {
            realtimeLogger.error("Failed to start audio engine: \(error.localizedDescription, privacy: .public)")
        }
    }

    private func stopAudioEngine() {
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
        audioConverter = nil
    }

    private func sendAudioBuffer(_ buffer: AVAudioPCMBuffer, targetFormat: AVAudioFormat) {
        guard let converter = audioConverter else { return }
        guard let outputBuffer = AVAudioPCMBuffer(
            pcmFormat: targetFormat,
            frameCapacity: AVAudioFrameCount(buffer.frameLength)
        ) else {
            return
        }

        var error: NSError?
        let inputBlock: AVAudioConverterInputBlock = { _, outStatus in
            outStatus.pointee = .haveData
            return buffer
        }

        converter.convert(to: outputBuffer, error: &error, withInputFrom: inputBlock)
        if let error {
            realtimeLogger.error("Audio conversion error: \(error.localizedDescription, privacy: .public)")
            return
        }

        let data: Data
        if let channelData = outputBuffer.int16ChannelData {
            data = Data(
                bytes: channelData[0],
                count: Int(outputBuffer.frameLength) * MemoryLayout<Int16>.size
            )
        } else {
            let audioBuffer = outputBuffer.audioBufferList.pointee.mBuffers
            guard let mData = audioBuffer.mData else { return }
            data = Data(bytes: mData, count: Int(audioBuffer.mDataByteSize))
        }

        let base64Audio = data.base64EncodedString()
        sendEvent(["type": "input_audio_buffer.append", "audio": base64Audio])
    }

    private func sendEvent(_ event: [String: Any]) {
        guard let webSocket else { return }
        guard let data = try? JSONSerialization.data(withJSONObject: event),
              let text = String(data: data, encoding: .utf8) else {
            return
        }

        webSocket.send(.string(text)) { [weak self] error in
            if let error {
                realtimeLogger.error("WebSocket send error: \(error.localizedDescription, privacy: .public)")
                self?.onError?(error.localizedDescription)
            }
        }
    }
}
