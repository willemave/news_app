//
//  DigestNarrationService.swift
//  newsly
//

import AVFoundation
import Foundation

@MainActor
final class NarrationPlaybackService: NSObject, ObservableObject, @preconcurrency AVAudioPlayerDelegate, @preconcurrency AVSpeechSynthesizerDelegate {
    static let shared = NarrationPlaybackService()
    nonisolated static let defaultPlaybackRate: Float = 1.0
    nonisolated static let longPressPlaybackRate: Float = 1.5

    @Published private(set) var isSpeaking = false
    @Published private(set) var playbackRate: Float = defaultPlaybackRate
    @Published private(set) var speakingTarget: NarrationTarget?

    private let synthesizer = AVSpeechSynthesizer()
    private var audioPlayer: AVAudioPlayer?
    private var cachedAudioByTarget: [NarrationTarget: Data] = [:]
    private var cachedTextByTarget: [NarrationTarget: String] = [:]
    private var cacheOrder: [NarrationTarget] = []
    private let maxCachedTargets = 12

    private override init() {
        super.init()
        synthesizer.delegate = self
    }

    func setPlaybackRate(_ rate: Float) {
        playbackRate = rate
        if let audioPlayer {
            audioPlayer.enableRate = true
            audioPlayer.rate = rate
        }
    }

    func playNarration(
        for target: NarrationTarget,
        rate: Float = defaultPlaybackRate,
        fetchAudio: () async throws -> Data,
        fetchNarrationText: () async throws -> String
    ) async throws {
        stop()
        setPlaybackRate(rate)

        if playCachedAudio(for: target) {
            return
        }

        do {
            let audioData = try await fetchAudio()
            try playAudio(audioData, for: target)
        } catch {
            let narrationText: String
            if let cachedText = cachedTextByTarget[target] {
                narrationText = cachedText
            } else {
                narrationText = try await fetchNarrationText()
                cacheText(narrationText, for: target)
            }
            speak(text: narrationText, for: target)
        }
    }

    func playCachedAudio(for target: NarrationTarget) -> Bool {
        guard let audioData = cachedAudioByTarget[target] else { return false }
        do {
            try playAudio(audioData, for: target)
            return true
        } catch {
            removeCachedAudio(for: target)
            return false
        }
    }

    func playAudio(_ audioData: Data, for target: NarrationTarget) throws {
        guard !audioData.isEmpty else {
            throw NSError(
                domain: "NarrationPlaybackService",
                code: 2,
                userInfo: [NSLocalizedDescriptionKey: "Narration audio was empty."]
            )
        }

        stop()
        cacheAudio(audioData, for: target)
        do {
            try configurePlaybackSession()

            let player = try AVAudioPlayer(data: audioData)
            player.delegate = self
            player.enableRate = true
            player.rate = playbackRate
            player.prepareToPlay()
            guard player.play() else {
                throw NSError(
                    domain: "NarrationPlaybackService",
                    code: 1,
                    userInfo: [
                        NSLocalizedDescriptionKey: "Failed to start narration audio playback."
                    ]
                )
            }

            audioPlayer = player
            speakingTarget = target
            isSpeaking = true
        } catch {
            resetPlaybackState()
            throw error
        }
    }

    func speak(text: String, for target: NarrationTarget) {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return }

        stop()
        cacheText(normalized, for: target)

        let utterance = AVSpeechUtterance(string: normalized)
        utterance.rate = min(
            AVSpeechUtteranceMaximumSpeechRate,
            AVSpeechUtteranceDefaultSpeechRate * (0.95 * playbackRate)
        )
        utterance.pitchMultiplier = 1.0
        utterance.volume = 1.0
        utterance.voice = AVSpeechSynthesisVoice(language: Locale.current.identifier)

        speakingTarget = target
        isSpeaking = true
        synthesizer.speak(utterance)
    }

    func stop() {
        if audioPlayer?.isPlaying == true {
            audioPlayer?.stop()
        }
        audioPlayer = nil
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        resetPlaybackState()
    }

    func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didFinish utterance: AVSpeechUtterance
    ) {
        let _ = utterance
        let _ = synthesizer
        resetPlaybackState()
    }

    func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didCancel utterance: AVSpeechUtterance
    ) {
        let _ = utterance
        let _ = synthesizer
        resetPlaybackState()
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        let _ = player
        let _ = flag
        resetPlaybackState()
    }

    func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        let _ = player
        let _ = error
        resetPlaybackState()
    }

    private func cacheAudio(_ audioData: Data, for target: NarrationTarget) {
        cachedAudioByTarget[target] = audioData
        touchCache(target)
    }

    private func cacheText(_ text: String, for target: NarrationTarget) {
        cachedTextByTarget[target] = text
        touchCache(target)
    }

    private func touchCache(_ target: NarrationTarget) {
        cacheOrder.removeAll { $0 == target }
        cacheOrder.append(target)
        while cacheOrder.count > maxCachedTargets {
            let evictedTarget = cacheOrder.removeFirst()
            cachedAudioByTarget.removeValue(forKey: evictedTarget)
            cachedTextByTarget.removeValue(forKey: evictedTarget)
        }
    }

    private func removeCachedAudio(for target: NarrationTarget) {
        cachedAudioByTarget.removeValue(forKey: target)
        cacheOrder.removeAll { $0 == target }
    }

    private func configurePlaybackSession() throws {
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.playback, mode: .default, options: [.duckOthers])
        try audioSession.setActive(true)
    }

    private func resetPlaybackState() {
        audioPlayer = nil
        isSpeaking = false
        speakingTarget = nil
        try? AVAudioSession.sharedInstance().setActive(
            false,
            options: [.notifyOthersOnDeactivation]
        )
    }
}
