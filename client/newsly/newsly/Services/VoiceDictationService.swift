//
//  VoiceDictationService.swift
//  newsly
//
//  Voice dictation service using OpenAI's gpt-4o-transcribe.
//

import AVFoundation
import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "VoiceDictation")

/// Error types for voice dictation.
enum VoiceDictationError: LocalizedError {
    case noAPIKey
    case recordingFailed
    case transcriptionFailed(String)
    case noMicrophoneAccess
    case audioSessionError(Error)

    var errorDescription: String? {
        switch self {
        case .noAPIKey:
            return "OpenAI API key not configured"
        case .recordingFailed:
            return "Failed to record audio"
        case .transcriptionFailed(let message):
            return "Transcription failed: \(message)"
        case .noMicrophoneAccess:
            return "Microphone access denied"
        case .audioSessionError(let error):
            return "Audio session error: \(error.localizedDescription)"
        }
    }
}

/// Service for voice dictation using OpenAI's gpt-4o-transcribe.
@MainActor
final class VoiceDictationService: NSObject, ObservableObject {
    static let shared = VoiceDictationService()

    @Published private(set) var isRecording = false
    @Published private(set) var isTranscribing = false

    private var audioRecorder: AVAudioRecorder?
    private var recordingURL: URL?

    private var openAIAPIKey: String? {
        // Try multiple sources for the API key:
        // 1. Keychain (received from server during auth)
        if let key = KeychainManager.shared.getToken(key: .openaiApiKey),
           !key.isEmpty {
            return key
        }
        // 2. Info.plist (from build settings/xcconfig) - fallback for development
        if let key = Bundle.main.object(forInfoDictionaryKey: "OPENAI_API_KEY") as? String,
           !key.isEmpty, !key.hasPrefix("$(") {
            return key
        }
        // 3. Environment variable (set in Xcode scheme for development)
        if let key = ProcessInfo.processInfo.environment["OPENAI_API_KEY"],
           !key.isEmpty {
            return key
        }
        return nil
    }

    private override init() {
        super.init()
    }

    /// Request microphone permission.
    func requestMicrophonePermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVAudioApplication.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
    }

    /// Start recording audio.
    func startRecording() async throws {
        guard openAIAPIKey != nil else {
            throw VoiceDictationError.noAPIKey
        }

        let hasPermission = await requestMicrophonePermission()
        guard hasPermission else {
            throw VoiceDictationError.noMicrophoneAccess
        }

        // Configure audio session
        let audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
            try audioSession.setActive(true)
        } catch {
            throw VoiceDictationError.audioSessionError(error)
        }

        // Create recording URL
        let documentsPath = FileManager.default.temporaryDirectory
        let audioFilename = documentsPath.appendingPathComponent("voice_dictation.m4a")
        recordingURL = audioFilename

        // Recording settings
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000.0,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]

        do {
            audioRecorder = try AVAudioRecorder(url: audioFilename, settings: settings)
            audioRecorder?.delegate = self
            audioRecorder?.record()
            isRecording = true
            logger.info("Started recording")
        } catch {
            throw VoiceDictationError.recordingFailed
        }
    }

    /// Stop recording and transcribe.
    func stopRecordingAndTranscribe() async throws -> String {
        guard isRecording, let recorder = audioRecorder else {
            throw VoiceDictationError.recordingFailed
        }

        recorder.stop()
        isRecording = false
        logger.info("Stopped recording")

        guard let url = recordingURL else {
            throw VoiceDictationError.recordingFailed
        }

        // Transcribe using OpenAI
        isTranscribing = true
        defer { isTranscribing = false }

        return try await transcribeAudio(fileURL: url)
    }

    /// Cancel recording without transcribing.
    func cancelRecording() {
        audioRecorder?.stop()
        audioRecorder = nil
        isRecording = false

        // Clean up recording file
        if let url = recordingURL {
            try? FileManager.default.removeItem(at: url)
        }
        recordingURL = nil
    }

    // MARK: - Private

    private func transcribeAudio(fileURL: URL) async throws -> String {
        guard let apiKey = openAIAPIKey else {
            throw VoiceDictationError.noAPIKey
        }

        let url = URL(string: "https://api.openai.com/v1/audio/transcriptions")!

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        // Build multipart form data
        var body = Data()

        // Add model field
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"model\"\r\n\r\n".data(using: .utf8)!)
        body.append("gpt-4o-transcribe\r\n".data(using: .utf8)!)

        // Add audio file
        let audioData = try Data(contentsOf: fileURL)
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"audio.m4a\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/m4a\r\n\r\n".data(using: .utf8)!)
        body.append(audioData)
        body.append("\r\n".data(using: .utf8)!)

        // Close boundary
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw VoiceDictationError.transcriptionFailed("Invalid response")
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            logger.error("Transcription failed: \(errorMessage)")
            throw VoiceDictationError.transcriptionFailed(errorMessage)
        }

        // Parse response
        struct TranscriptionResponse: Codable {
            let text: String
        }

        let decoder = JSONDecoder()
        let transcriptionResponse = try decoder.decode(TranscriptionResponse.self, from: data)

        // Clean up recording file
        try? FileManager.default.removeItem(at: fileURL)

        logger.info("Transcription successful: \(transcriptionResponse.text.prefix(50))...")
        return transcriptionResponse.text
    }
}

// MARK: - AVAudioRecorderDelegate

extension VoiceDictationService: AVAudioRecorderDelegate {
    nonisolated func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        Task { @MainActor in
            if !flag {
                logger.error("Recording did not finish successfully")
            }
        }
    }

    nonisolated func audioRecorderEncodeErrorDidOccur(_ recorder: AVAudioRecorder, error: Error?) {
        Task { @MainActor in
            if let error = error {
                logger.error("Recording encode error: \(error.localizedDescription)")
            }
        }
    }
}
