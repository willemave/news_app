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
            guard !self.engine.isRunning else { return }
            do {
                try self.engine.start()
            } catch {
                return
            }
            if !self.playerNode.isPlaying {
                self.playerNode.play()
            }
        }
    }

    func stop() {
        queue.async {
            self.playerNode.stop()
            self.engine.stop()
        }
    }

    func enqueuePCM16Base64(_ audioB64: String) {
        guard let data = Data(base64Encoded: audioB64), !data.isEmpty else { return }
        enqueuePCM16Data(data)
    }

    func enqueuePCM16Data(_ data: Data) {
        queue.async {
            guard self.engine.isRunning else { return }
            let frameCount = data.count / MemoryLayout<Int16>.size
            guard frameCount > 0 else { return }
            guard let buffer = AVAudioPCMBuffer(
                pcmFormat: self.playbackFormat,
                frameCapacity: AVAudioFrameCount(frameCount)
            ) else { return }

            buffer.frameLength = AVAudioFrameCount(frameCount)
            data.withUnsafeBytes { rawBuffer in
                guard let src = rawBuffer.baseAddress else { return }
                if let channelData = buffer.int16ChannelData?.pointee {
                    channelData.assign(from: src.assumingMemoryBound(to: Int16.self), count: frameCount)
                }
            }

            if !self.playerNode.isPlaying {
                self.playerNode.play()
            }
            self.playerNode.scheduleBuffer(buffer, completionHandler: nil)

            let energy = VoiceFFTAnalyzer.normalizedEnergy(fromPCM16: data)
            DispatchQueue.main.async {
                self.onEnergySample?(energy)
            }
        }
    }
}
