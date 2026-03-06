//
//  DigestNarrationService.swift
//  newsly
//

import AVFoundation
import Foundation

@MainActor
final class DigestNarrationService: NSObject, ObservableObject, @preconcurrency AVAudioPlayerDelegate, @preconcurrency AVSpeechSynthesizerDelegate {
    static let shared = DigestNarrationService()
    static let supportedPlaybackRates: [Float] = [1.0, 1.25, 1.5, 1.75, 2.0]

    @Published private(set) var isSpeaking = false
    @Published private(set) var playbackRate: Float = 1.0
    @Published private(set) var speakingDigestId: Int?

    private let synthesizer = AVSpeechSynthesizer()
    private var audioPlayer: AVAudioPlayer?
    private var cachedAudioByDigestId: [Int: Data] = [:]
    private var cacheOrder: [Int] = []
    private let maxCachedDigests = 12

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

    func playCachedAudio(for digestId: Int) -> Bool {
        guard let audioData = cachedAudioByDigestId[digestId] else { return false }
        do {
            try playAudio(audioData, digestId: digestId)
            return true
        } catch {
            removeCachedAudio(for: digestId)
            return false
        }
    }

    func playAudio(_ audioData: Data, digestId: Int) throws {
        guard !audioData.isEmpty else {
            throw NSError(
                domain: "DigestNarrationService",
                code: 2,
                userInfo: [NSLocalizedDescriptionKey: "Digest narration audio was empty."]
            )
        }

        stop()
        cacheAudio(audioData, for: digestId)
        do {
            try configurePlaybackSession()

            let player = try AVAudioPlayer(data: audioData)
            player.delegate = self
            player.enableRate = true
            player.rate = playbackRate
            player.prepareToPlay()
            guard player.play() else {
                throw NSError(
                    domain: "DigestNarrationService",
                    code: 1,
                    userInfo: [
                        NSLocalizedDescriptionKey: "Failed to start digest narration audio playback."
                    ]
                )
            }

            audioPlayer = player
            speakingDigestId = digestId
            isSpeaking = true
        } catch {
            resetPlaybackState()
            throw error
        }
    }

    func speak(text: String, digestId: Int) {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return }

        stop()

        let utterance = AVSpeechUtterance(string: normalized)
        utterance.rate = min(
            AVSpeechUtteranceMaximumSpeechRate,
            AVSpeechUtteranceDefaultSpeechRate * (0.95 * playbackRate)
        )
        utterance.pitchMultiplier = 1.0
        utterance.volume = 1.0
        utterance.voice = AVSpeechSynthesisVoice(language: Locale.current.identifier)

        speakingDigestId = digestId
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

    private func cacheAudio(_ audioData: Data, for digestId: Int) {
        cachedAudioByDigestId[digestId] = audioData
        cacheOrder.removeAll { $0 == digestId }
        cacheOrder.append(digestId)
        while cacheOrder.count > maxCachedDigests {
            let evictedDigestId = cacheOrder.removeFirst()
            cachedAudioByDigestId.removeValue(forKey: evictedDigestId)
        }
    }

    private func removeCachedAudio(for digestId: Int) {
        cachedAudioByDigestId.removeValue(forKey: digestId)
        cacheOrder.removeAll { $0 == digestId }
    }

    private func configurePlaybackSession() throws {
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.playback, mode: .default, options: [.duckOthers])
        try audioSession.setActive(true)
    }

    private func resetPlaybackState() {
        audioPlayer = nil
        isSpeaking = false
        speakingDigestId = nil
        try? AVAudioSession.sharedInstance().setActive(
            false,
            options: [.notifyOthersOnDeactivation]
        )
    }
}
