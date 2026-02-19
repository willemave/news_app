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
    private let simulatorPreferredInputEnvKey = "NEWSLY_SIM_AUDIO_INPUT"
    private let simulatorLoopbackInputHint = "BlackHole"

    private var converter: AVAudioConverter?
    private var isCapturing = false
    private var isStartingCapture = false
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
        guard !isStartingCapture else { return }
        isStartingCapture = true
        defer { isStartingCapture = false }
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
        isStartingCapture = false
        guard isCapturing else { return }
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        converter = nil
        isCapturing = false
        logger.info("Audio capture stopped")
    }

    private func configureAudioSession() throws {
        let audioSession = AVAudioSession.sharedInstance()
        #if targetEnvironment(simulator)
        let mode: AVAudioSession.Mode = .measurement
        let options: AVAudioSession.CategoryOptions = [.mixWithOthers]
        #else
        let mode: AVAudioSession.Mode = .voiceChat
        let options: AVAudioSession.CategoryOptions = [.defaultToSpeaker, .allowBluetoothHFP]
        #endif
        try audioSession.setCategory(
            .playAndRecord,
            mode: mode,
            options: options
        )
        try audioSession.setPreferredSampleRate(targetSampleRate)
        try audioSession.setPreferredIOBufferDuration(0.02)
        try audioSession.setActive(true)
        #if targetEnvironment(simulator)
        try configureSimulatorPreferredInput(audioSession)
        #endif
        logCurrentRoute(audioSession)
        logger.debug("Audio session configured for live voice capture")
    }

    #if targetEnvironment(simulator)
    private func configureSimulatorPreferredInput(_ audioSession: AVAudioSession) throws {
        guard let availableInputs = audioSession.availableInputs, !availableInputs.isEmpty else {
            logger.warning("Simulator audio input list is empty")
            return
        }

        let inputList = availableInputs
            .map { "\($0.portName) [\($0.portType.rawValue)]" }
            .joined(separator: ", ")
        logger.info("Simulator available audio inputs | inputs=\(inputList, privacy: .public)")

        let requestedInput = ProcessInfo.processInfo.environment[simulatorPreferredInputEnvKey]?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let preferredInput =
            selectPreferredInput(availableInputs: availableInputs, requestedInput: requestedInput)
        guard let preferredInput else { return }

        try audioSession.setPreferredInput(preferredInput)
        logger.info(
            "Simulator preferred input selected | port=\(preferredInput.portName, privacy: .public) uid=\(preferredInput.uid, privacy: .public)"
        )
    }

    private func selectPreferredInput(
        availableInputs: [AVAudioSessionPortDescription],
        requestedInput: String?
    ) -> AVAudioSessionPortDescription? {
        guard let requestedInput, !requestedInput.isEmpty else {
            return availableInputs.first {
                $0.portName.localizedCaseInsensitiveContains(simulatorLoopbackInputHint)
            }
        }
        return availableInputs.first {
            $0.portName.localizedCaseInsensitiveContains(requestedInput)
                || $0.uid.localizedCaseInsensitiveContains(requestedInput)
        }
    }
    #endif

    private func logCurrentRoute(_ audioSession: AVAudioSession) {
        let inputSummary = audioSession.currentRoute.inputs
            .map { "\($0.portName) [\($0.portType.rawValue)]" }
            .joined(separator: ", ")
        let outputSummary = audioSession.currentRoute.outputs
            .map { "\($0.portName) [\($0.portType.rawValue)]" }
            .joined(separator: ", ")
        logger.info(
            "Audio route | mode=\(audioSession.mode.rawValue, privacy: .public) category=\(audioSession.category.rawValue, privacy: .public) sampleRate=\(audioSession.sampleRate, privacy: .public) inputs=\(inputSummary, privacy: .public) outputs=\(outputSummary, privacy: .public)"
        )
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
        var hasProvidedInput = false
        let inputBlock: AVAudioConverterInputBlock = { _, outStatus in
            guard !hasProvidedInput else {
                outStatus.pointee = .noDataNow
                return nil
            }
            hasProvidedInput = true
            outStatus.pointee = .haveData
            return buffer
        }
        let conversionStatus = converter.convert(
            to: outputBuffer,
            error: &error,
            withInputFrom: inputBlock
        )
        if error != nil {
            return
        }
        guard conversionStatus == .haveData || conversionStatus == .inputRanDry else { return }

        guard let channelData = outputBuffer.int16ChannelData?.pointee else { return }
        let frameLength = Int(outputBuffer.frameLength)
        let channelCount = Int(outputBuffer.format.channelCount)
        guard frameLength > 0 else { return }
        guard channelCount > 0 else { return }

        let sampleCount = frameLength * channelCount
        let data = Data(
            bytes: channelData,
            count: sampleCount * MemoryLayout<Int16>.size
        )
        let b64 = data.base64EncodedString()
        var sumSquares: Float = 0
        for index in 0..<sampleCount {
            let normalized = Float(channelData[index]) / Float(Int16.max)
            sumSquares += normalized * normalized
        }
        let rms = sqrt(sumSquares / Float(sampleCount))
        capturedBufferCount += 1
        if capturedBufferCount == 1 || capturedBufferCount % diagnosticsFrameLogInterval == 0 {
            logger.debug(
                "Capture diagnostics | buffer=\(self.capturedBufferCount) frameLength=\(frameLength) rms=\(rms, privacy: .public)"
            )
        }
        onAudioFrame?(b64, rms)
    }
}
