//
//  LiveVoiceAudioPlaybackEngine.swift
//  newsly
//

import AVFoundation
import Foundation

final class LiveVoiceAudioPlaybackEngine {
    var onEnergySample: ((Float) -> Void)?

    private let engine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private let queue = DispatchQueue(label: "com.newsly.livevoice.playback")
    private let sampleRate: Double = 16_000
    private let channels: AVAudioChannelCount = 1
    private let maxPendingBuffers = 64
    private var pendingBuffers: [Data] = []

    private lazy var playbackFormat: AVAudioFormat = {
        AVAudioFormat(
            commonFormat: .pcmFormatInt16,
            sampleRate: sampleRate,
            channels: channels,
            interleaved: true
        )!
    }()

    init() {
        engine.attach(playerNode)
        engine.connect(playerNode, to: engine.mainMixerNode, format: playbackFormat)
    }

    func start() {
        queue.async {
            self.startEngineIfNeeded()
            self.flushPendingBuffers()
        }
    }

    func stop() {
        queue.async {
            self.playerNode.stop()
            self.engine.stop()
        }
    }

    /// Immediately stop playback and discard all pending buffers,
    /// but keep the engine running so new audio can be scheduled later.
    func flush() {
        queue.async {
            self.pendingBuffers.removeAll(keepingCapacity: true)
            self.playerNode.stop()
            if self.engine.isRunning {
                self.playerNode.play()
            }
        }
    }

    func enqueuePCM16Base64(_ audioB64: String) {
        guard let data = Data(base64Encoded: audioB64), !data.isEmpty else { return }
        enqueuePCM16Data(data)
    }

    func enqueuePCM16Data(_ data: Data) {
        queue.async {
            guard !data.isEmpty else { return }
            if !self.engine.isRunning {
                if self.pendingBuffers.count >= self.maxPendingBuffers {
                    self.pendingBuffers.removeFirst(self.pendingBuffers.count - self.maxPendingBuffers + 1)
                }
                self.pendingBuffers.append(data)
                self.startEngineIfNeeded()
                self.flushPendingBuffers()
                return
            }
            self.schedulePCM16Data(data)
        }
    }

    private func startEngineIfNeeded() {
        guard !engine.isRunning else {
            if !playerNode.isPlaying {
                playerNode.play()
            }
            return
        }
        do {
            try engine.start()
        } catch {
            return
        }
        if !playerNode.isPlaying {
            playerNode.play()
        }
    }

    private func flushPendingBuffers() {
        guard engine.isRunning, !pendingBuffers.isEmpty else { return }
        let buffered = pendingBuffers
        pendingBuffers.removeAll(keepingCapacity: true)
        for chunk in buffered {
            schedulePCM16Data(chunk)
        }
    }

    private func schedulePCM16Data(_ data: Data) {
        let frameCount = data.count / MemoryLayout<Int16>.size
        guard frameCount > 0 else { return }
        guard let buffer = AVAudioPCMBuffer(
            pcmFormat: playbackFormat,
            frameCapacity: AVAudioFrameCount(frameCount)
        ) else { return }

        buffer.frameLength = AVAudioFrameCount(frameCount)
        data.withUnsafeBytes { rawBuffer in
            guard let src = rawBuffer.baseAddress else { return }
            if let channelData = buffer.int16ChannelData?.pointee {
                channelData.assign(from: src.assumingMemoryBound(to: Int16.self), count: frameCount)
            }
        }

        if !playerNode.isPlaying {
            playerNode.play()
        }
        playerNode.scheduleBuffer(buffer, completionHandler: nil)

        let energy = VoiceFFTAnalyzer.normalizedEnergy(fromPCM16: data)
        DispatchQueue.main.async {
            self.onEnergySample?(energy)
        }
    }
}
