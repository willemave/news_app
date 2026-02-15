//
//  LiveVoiceAudioCaptureEngine.swift
//  newsly
//

import AVFoundation
import Foundation
import os.log

enum LiveVoiceAudioCaptureError: LocalizedError {
    case microphoneDenied
    case conversionFailed

    var errorDescription: String? {
        switch self {
        case .microphoneDenied:
            return "Microphone access is required for Live Voice."
        case .conversionFailed:
            return "Failed to process microphone audio."
        }
    }
}

final class LiveVoiceAudioCaptureEngine {
    var onAudioFrame: ((String, Float) -> Void)?

    private let engine = AVAudioEngine()
    private let processingQueue = DispatchQueue(label: "com.newsly.livevoice.capture")
    private let targetSampleRate: Double = 16_000
    private let logger = Logger(subsystem: "com.newsly", category: "LiveVoiceCapture")
    private let diagnosticsFrameLogInterval = 50

    private var converter: AVAudioConverter?
    private var isCapturing = false
    private var capturedBufferCount = 0

    func requestMicrophonePermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVAudioApplication.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
    }

    func startCapture() async throws {
        guard !isCapturing else { return }
        let hasPermission = await requestMicrophonePermission()
        guard hasPermission else {
            logger.error("Microphone permission denied")
            throw LiveVoiceAudioCaptureError.microphoneDenied
        }

        try configureAudioSession()
        let inputNode = engine.inputNode
        let inputFormat = inputNode.outputFormat(forBus: 0)
        capturedBufferCount = 0

        guard let targetFormat = AVAudioFormat(
            commonFormat: .pcmFormatInt16,
            sampleRate: targetSampleRate,
            channels: 1,
            interleaved: true
        ),
              let converter = AVAudioConverter(from: inputFormat, to: targetFormat) else {
            logger.error("Failed to build AVAudioConverter")
            throw LiveVoiceAudioCaptureError.conversionFailed
        }

        self.converter = converter
        logger.info(
            "Capture input format | sampleRate=\(inputFormat.sampleRate, privacy: .public) channels=\(inputFormat.channelCount)"
        )
        inputNode.removeTap(onBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: inputFormat) { [weak self] buffer, _ in
            self?.processingQueue.async {
                self?.processBuffer(buffer, targetFormat: targetFormat)
            }
        }

        try engine.start()
        isCapturing = true
        logger.info("Audio capture started")
    }

    func stopCapture() {
        guard isCapturing else { return }
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        converter = nil
        isCapturing = false
        logger.info("Audio capture stopped")
    }

    private func configureAudioSession() throws {
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(
            .playAndRecord,
            mode: .voiceChat,
            options: [.defaultToSpeaker, .allowBluetooth, .allowBluetoothA2DP]
        )
        try audioSession.setPreferredSampleRate(targetSampleRate)
        try audioSession.setPreferredIOBufferDuration(0.02)
        try audioSession.setActive(true)
        logger.debug("Audio session configured for live voice capture")
    }

    private func processBuffer(_ buffer: AVAudioPCMBuffer, targetFormat: AVAudioFormat) {
        guard let converter else { return }
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
        if error != nil {
            return
        }

        guard let channelData = outputBuffer.int16ChannelData?.pointee else { return }
        let frameLength = Int(outputBuffer.frameLength)
        guard frameLength > 0 else { return }

        let data = Data(
            bytes: channelData,
            count: frameLength * MemoryLayout<Int16>.size
        )
        let b64 = data.base64EncodedString()
        var sumSquares: Float = 0
        for index in 0..<frameLength {
            let normalized = Float(channelData[index]) / Float(Int16.max)
            sumSquares += normalized * normalized
        }
        let rms = sqrt(sumSquares / Float(frameLength))
        capturedBufferCount += 1
        if capturedBufferCount == 1 || capturedBufferCount % diagnosticsFrameLogInterval == 0 {
            logger.debug(
                "Capture diagnostics | buffer=\(self.capturedBufferCount) frameLength=\(frameLength) rms=\(rms, privacy: .public)"
            )
        }
        DispatchQueue.main.async {
            self.onAudioFrame?(b64, rms)
        }
    }
}
