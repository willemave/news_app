//
//  LiveVoiceViewModel.swift
//  newsly
//

import Foundation
import os.log

private let liveVoiceLogger = Logger(subsystem: "com.newsly", category: "LiveVoiceViewModel")

@MainActor
final class LiveVoiceViewModel: ObservableObject {
    enum ConnectionState: Equatable {
        case idle
        case connecting
        case connected
        case failed(String)
    }

    @Published private(set) var connectionState: ConnectionState = .idle
    @Published private(set) var isListening = false
    @Published private(set) var isAssistantSpeaking = false
    @Published private(set) var transcriptPartial = ""
    @Published private(set) var transcriptFinal = ""
    @Published private(set) var assistantText = ""
    @Published private(set) var statusMessage = "Connect to start Live Voice."
    @Published private(set) var sessionId: String?
    @Published private(set) var chatSessionId: Int?
    @Published private(set) var sphereEnergy: Float = 0
    @Published private(set) var isAwaitingAssistant = false
    @Published private(set) var debugPhase = "Idle"
    @Published private(set) var debugLastServerEvent = "-"
    @Published private(set) var debugLastClientAction = "-"
    @Published private(set) var debugCurrentTurnId: String?
    @Published private(set) var debugEventTimeline: [String] = []

    private let sessionService = VoiceSessionService.shared
    private let websocketClient = VoiceWebSocketClient()
    private let captureEngine = LiveVoiceAudioCaptureEngine()
    private let playbackEngine = LiveVoiceAudioPlaybackEngine()
    private let autoTurnsEnabled = true

    private var frameSequence = 0
    private var currentRoute: LiveVoiceRoute?
    private var currentTurnId: String?
    private var introTurnId: String?
    private var pendingIntroAck = false
    private var introHadAudio = false
    private var currentTurnFrameCount = 0
    private var listeningStartedAt: Date?
    private var pendingAudioFrameSends = 0
    private var audioFrameSendChain: Task<Void, Never>?
    private var isAutoReconnecting = false
    private var shouldAutoStartListeningOnReady = false
    private var shouldAutoStartListeningAfterTurn = false
    private var didReceiveSessionReady = false
    private var maxTurnDurationSeconds: TimeInterval = 18
    private var hasDetectedSpeechInTurn = false
    private var speechFramesInTurn = 0
    private var consecutiveSpeechFrames = 0
    private var peakSpeechRmsInTurn: Float = 0
    private var hasTranscriptActivityInTurn = false
    private var lastSpeechAt: Date?
    private var trailingSilenceFramesRemaining = 0
    private var isAutoCommittingTurn = false
    private var adaptiveNoiseFloorRms: Float = 0.004
    private var remainingNoiseCalibrationFrames = 0
    private var peakObservedRmsInTurn: Float = 0
    private var lastObservedRms: Float = 0
    private var lastDynamicSpeechThreshold: Float = 0
    private var diagnosticsFrameCounter = 0

    private let minimumCommitDurationSeconds: TimeInterval = 0.7
    private let postCaptureFlushDelayNanos: UInt64 = 120_000_000
    private let maxCommitWaitNanos: UInt64 = 350_000_000
    private let commitPollIntervalNanos: UInt64 = 20_000_000
    private let minimumSpeechRmsThreshold: Float = 0.014
    private let minimumTranscriptRmsSignal: Float = 0.008
    private let strongSpeechRmsThreshold: Float = 0.055
    private let immediateSpeechRmsThreshold: Float = 0.04
    private let noiseFloorSmoothing: Float = 0.04
    private let speechOverNoiseMultiplier: Float = 3.0
    private let noiseCalibrationFrames = 20
    private let speechStartConsecutiveFrames = 3
    private let minimumSpeechFramesForCommit = 8
    private let silenceAutoCommitSeconds: TimeInterval = 1.7
    private let trailingSilenceFrames = 8

    private static let debugTimeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "HH:mm:ss.SSS"
        return formatter
    }()

    init() {
        configureCallbacks()
    }

    var canConnect: Bool {
        if case .connecting = connectionState {
            return false
        }
        if case .connected = connectionState {
            return false
        }
        return true
    }

    func connect(route: LiveVoiceRoute?) async {
        if case .connected = connectionState {
            return
        }
        pushDebugEvent("connect requested")
        currentRoute = route
        connectionState = .connecting
        statusMessage = "Connecting..."
        refreshDebugPhase()
        liveVoiceLogger.info(
            "Live connect start | routeContentId=\(route?.contentId ?? -1) routeChatSessionId=\(route?.chatSessionId ?? -1) mode=\(route?.launchMode.rawValue ?? "general", privacy: .public)"
        )
        liveVoiceLogger.info("Live connect baseURL: \(AppSettings.shared.baseURL, privacy: .public)")

        do {
            let user = try await AuthenticationService.shared.getCurrentUser()
            let token = try await sessionService.fetchAccessToken()

            let launchMode = route?.launchMode ?? .general
            let sourceSurface = route?.sourceSurface ?? .knowledgeLive
            let requestIntro = !user.hasCompletedLiveVoiceOnboarding
            didReceiveSessionReady = false
            shouldAutoStartListeningOnReady = autoTurnsEnabled && !requestIntro && launchMode != .dictateSummary
            shouldAutoStartListeningAfterTurn = autoTurnsEnabled || launchMode == .dictateSummary || requestIntro
            let request = VoiceCreateSessionRequest(
                sessionId: route?.sessionId,
                sampleRateHz: 16_000,
                contentId: route?.contentId,
                chatSessionId: route?.chatSessionId,
                launchMode: launchMode,
                sourceSurface: sourceSurface,
                requestIntro: requestIntro
            )

            let sessionResponse = try await sessionService.createSession(request)
            let wsURL = try sessionService.resolveWebSocketURL(path: sessionResponse.websocketPath)
            liveVoiceLogger.info(
                "Live session created | sessionId=\(sessionResponse.sessionId, privacy: .public) chatSessionId=\(sessionResponse.chatSessionId) ws=\(wsURL.absoluteString, privacy: .public)"
            )

            sessionId = sessionResponse.sessionId
            chatSessionId = sessionResponse.chatSessionId
            maxTurnDurationSeconds = TimeInterval(max(5, sessionResponse.maxInputSeconds))
            websocketClient.connect(url: wsURL, bearerToken: token)
            try await sendJSON(
                [
                    "type": "session.start",
                    "session_id": sessionResponse.sessionId
                ]
            )

            playbackEngine.start()
            connectionState = .connected
            statusMessage = "Connected"
            maybeAutoStartListening(reason: "session.ready")
            setAwaitingAssistant(false, reason: "connect complete")
            refreshDebugPhase()
            pushDebugEvent("session connected")
            liveVoiceLogger.info("Live voice connected")
        } catch {
            liveVoiceLogger.error("Failed to connect live voice: \(error.localizedDescription, privacy: .public)")
            connectionState = .failed(error.localizedDescription)
            statusMessage = error.localizedDescription
            setAwaitingAssistant(false, reason: "connect failed")
            refreshDebugPhase()
            pushDebugEvent("connect failed: \(error.localizedDescription)")
        }
    }

    func disconnect() async {
        pushDebugEvent("disconnect requested")
        if isListening {
            await stopListening(reason: "disconnect")
        }
        do {
            try await sendJSON(["type": "session.end"])
        } catch {
            liveVoiceLogger.debug("session.end send failed: \(error.localizedDescription, privacy: .public)")
        }
        websocketClient.disconnect()
        playbackEngine.stop()
        connectionState = .idle
        statusMessage = "Disconnected"
        currentTurnFrameCount = 0
        listeningStartedAt = nil
        pendingAudioFrameSends = 0
        isAutoReconnecting = false
        shouldAutoStartListeningOnReady = false
        shouldAutoStartListeningAfterTurn = false
        didReceiveSessionReady = false
        setAwaitingAssistant(false, reason: "disconnected")
        refreshDebugPhase()
    }

    func startListening() async {
        guard case .connected = connectionState else { return }
        guard !isListening else { return }
        guard !isAwaitingAssistant else {
            statusMessage = "Waiting for response..."
            return
        }
        guard !isAssistantSpeaking else {
            statusMessage = "Assistant speaking..."
            return
        }
        guard !isAutoCommittingTurn else { return }
        pushDebugEvent("listening start requested")
        frameSequence = 0
        currentTurnFrameCount = 0
        pendingAudioFrameSends = 0
        audioFrameSendChain = nil
        listeningStartedAt = Date()
        hasDetectedSpeechInTurn = false
        speechFramesInTurn = 0
        consecutiveSpeechFrames = 0
        peakSpeechRmsInTurn = 0
        peakObservedRmsInTurn = 0
        hasTranscriptActivityInTurn = false
        lastSpeechAt = nil
        trailingSilenceFramesRemaining = 0
        remainingNoiseCalibrationFrames = noiseCalibrationFrames
        isAutoCommittingTurn = false
        diagnosticsFrameCounter = 0
        peakObservedRmsInTurn = 0
        lastObservedRms = 0
        lastDynamicSpeechThreshold = minimumSpeechRmsThreshold
        transcriptPartial = ""
        transcriptFinal = ""
        do {
            try await captureEngine.startCapture()
            isListening = true
            statusMessage = "Listening..."
            setAwaitingAssistant(false, reason: "capturing audio")
            refreshDebugPhase()
            pushDebugEvent("listening started")
            liveVoiceLogger.info("Listening started")
        } catch {
            connectionState = .failed(error.localizedDescription)
            statusMessage = error.localizedDescription
            setAwaitingAssistant(false, reason: "listening failed")
            refreshDebugPhase()
            pushDebugEvent("listening failed: \(error.localizedDescription)")
            liveVoiceLogger.error("Failed to start listening: \(error.localizedDescription, privacy: .public)")
        }
    }

    func stopListening(reason: String = "manual") async {
        guard isListening else { return }
        let isAutomaticStop = reason != "manual"
        isAutoCommittingTurn = isAutomaticStop
        defer {
            isAutoCommittingTurn = false
        }
        captureEngine.stopCapture()
        isListening = false

        let listeningDuration = Date().timeIntervalSince(listeningStartedAt ?? Date())
        let hasTranscriptSignal = hasTranscriptActivityInTurn && peakObservedRmsInTurn >= minimumTranscriptRmsSignal
        let hasStrongSpeechSignal = hasTranscriptSignal || peakSpeechRmsInTurn >= strongSpeechRmsThreshold
        let hasCommitEligibleSpeech = hasTranscriptSignal
            || (
                hasDetectedSpeechInTurn
                    && speechFramesInTurn >= minimumSpeechFramesForCommit
                    && hasStrongSpeechSignal
            )
        let hasCommitEligibleAudio = currentTurnFrameCount > 0
            && listeningDuration >= minimumCommitDurationSeconds
            && hasCommitEligibleSpeech
        liveVoiceLogger.info(
            "Stop listening requested | reason=\(reason, privacy: .public) duration=\(listeningDuration, privacy: .public) frameCount=\(self.currentTurnFrameCount) speechFrames=\(self.speechFramesInTurn) speechDetected=\(self.hasDetectedSpeechInTurn) transcriptActivity=\(self.hasTranscriptActivityInTurn) transcriptSignal=\(hasTranscriptSignal) peakObservedRms=\(self.peakObservedRmsInTurn, privacy: .public) peakSpeechRms=\(self.peakSpeechRmsInTurn, privacy: .public) lastRms=\(self.lastObservedRms, privacy: .public) threshold=\(self.lastDynamicSpeechThreshold, privacy: .public) pendingFrameSends=\(self.pendingAudioFrameSends)"
        )
        if !hasCommitEligibleAudio {
            statusMessage = isAutomaticStop ? "Listening..." : "Keep speaking a little longer."
            transcriptPartial = ""
            listeningStartedAt = nil
            currentTurnFrameCount = 0
            hasDetectedSpeechInTurn = false
            speechFramesInTurn = 0
            consecutiveSpeechFrames = 0
            peakSpeechRmsInTurn = 0
            peakObservedRmsInTurn = 0
            hasTranscriptActivityInTurn = false
            lastSpeechAt = nil
            trailingSilenceFramesRemaining = 0
            remainingNoiseCalibrationFrames = noiseCalibrationFrames
            setAwaitingAssistant(false, reason: "insufficient audio")
            refreshDebugPhase()
            pushDebugEvent("commit skipped: insufficient audio")
            liveVoiceLogger.debug(
                "Skipping commit: insufficient captured audio | reason=\(reason, privacy: .public) frameCount=\(self.currentTurnFrameCount) speechFrames=\(self.speechFramesInTurn) speechDetected=\(self.hasDetectedSpeechInTurn) transcriptActivity=\(self.hasTranscriptActivityInTurn) peakRms=\(self.peakSpeechRmsInTurn, privacy: .public) lastRms=\(self.lastObservedRms, privacy: .public) threshold=\(self.lastDynamicSpeechThreshold, privacy: .public)"
            )
            if isAutomaticStop {
                autoResumeListening(reason: "insufficient audio")
            }
            return
        }

        let waitDeadline = DispatchTime.now().uptimeNanoseconds + maxCommitWaitNanos
        while pendingAudioFrameSends > 0, DispatchTime.now().uptimeNanoseconds < waitDeadline {
            try? await Task.sleep(nanoseconds: commitPollIntervalNanos)
        }
        try? await Task.sleep(nanoseconds: postCaptureFlushDelayNanos)
        liveVoiceLogger.info("Sending audio.commit | seq=\(self.frameSequence)")

        statusMessage = "Thinking..."
        listeningStartedAt = nil
        setAwaitingAssistant(true, reason: "audio.commit pending")
        refreshDebugPhase()
        pushDebugEvent("audio.commit sent")
        do {
            try await sendJSON(
                [
                    "type": "audio.commit",
                    "seq": frameSequence
                ]
            )
            currentTurnFrameCount = 0
            hasDetectedSpeechInTurn = false
            speechFramesInTurn = 0
            consecutiveSpeechFrames = 0
            peakSpeechRmsInTurn = 0
            peakObservedRmsInTurn = 0
            hasTranscriptActivityInTurn = false
            lastSpeechAt = nil
            trailingSilenceFramesRemaining = 0
            remainingNoiseCalibrationFrames = noiseCalibrationFrames
        } catch {
            connectionState = .failed(error.localizedDescription)
            statusMessage = error.localizedDescription
            setAwaitingAssistant(false, reason: "audio.commit failed")
            refreshDebugPhase()
            pushDebugEvent("audio.commit failed: \(error.localizedDescription)")
        }
    }

    func cancelResponse() async {
        pushDebugEvent("cancel response requested")
        do {
            try await sendJSON(["type": "response.cancel"])
            setAwaitingAssistant(false, reason: "response cancelled")
            refreshDebugPhase()
        } catch {
            liveVoiceLogger.debug("response.cancel send failed: \(error.localizedDescription, privacy: .public)")
        }
    }

    private func configureCallbacks() {
        captureEngine.onAudioFrame = { [weak self] frameB64, rms in
            guard let self else { return }
            Task { @MainActor in
                await self.handleCapturedFrame(frameB64: frameB64, rms: rms)
            }
        }

        playbackEngine.onEnergySample = { [weak self] energy in
            guard let self else { return }
            self.sphereEnergy = energy
        }

        websocketClient.onEvent = { [weak self] event in
            guard let self else { return }
            self.handleEvent(event)
        }
        websocketClient.onRawEvent = { [weak self] payload in
            guard let self else { return }
            self.handleRawEvent(payload)
        }
        websocketClient.onError = { [weak self] message in
            guard let self else { return }
            let normalized = message.lowercased()
            self.debugLastServerEvent = "ws.error"
            self.pushDebugEvent("ws error: \(message)")
            if normalized.contains("connection refused") {
                let friendly = "Cannot reach \(AppSettings.shared.baseURL). Start server or check host/port."
                self.connectionState = .failed(friendly)
                self.statusMessage = friendly
                self.setAwaitingAssistant(false, reason: "connection refused")
            } else if normalized.contains("socket is not connected") {
                self.statusMessage = "Connection lost. Reconnecting..."
                if !self.isAutoReconnecting {
                    Task { @MainActor in
                        await self.reconnectCurrentSession()
                    }
                }
            } else {
                self.connectionState = .failed(message)
                self.statusMessage = message
                self.setAwaitingAssistant(false, reason: "websocket error")
            }
            self.refreshDebugPhase()
            liveVoiceLogger.error("Websocket error callback: \(message, privacy: .public)")
        }
        websocketClient.onDisconnected = { [weak self] in
            guard let self else { return }
            if case .failed = self.connectionState {
                return
            }
            self.connectionState = .idle
            self.statusMessage = "Disconnected"
            self.isListening = false
            self.isAssistantSpeaking = false
            self.setAwaitingAssistant(false, reason: "websocket disconnected")
            self.refreshDebugPhase()
            self.pushDebugEvent("ws disconnected")
        }
    }

    private func handleCapturedFrame(frameB64: String, rms: Float) async {
        guard case .connected = connectionState else { return }
        guard isListening else { return }

        let now = Date()
        if remainingNoiseCalibrationFrames > 0 {
            adaptiveNoiseFloorRms = (1 - noiseFloorSmoothing) * adaptiveNoiseFloorRms + noiseFloorSmoothing * rms
            remainingNoiseCalibrationFrames -= 1
        } else if !hasDetectedSpeechInTurn || !hasTranscriptActivityInTurn {
            adaptiveNoiseFloorRms = (1 - noiseFloorSmoothing) * adaptiveNoiseFloorRms + noiseFloorSmoothing * rms
        }
        let dynamicSpeechThreshold = max(
            minimumSpeechRmsThreshold,
            adaptiveNoiseFloorRms * speechOverNoiseMultiplier
        )
        let requiredSpeechThreshold =
            remainingNoiseCalibrationFrames > 0 ? max(dynamicSpeechThreshold, immediateSpeechRmsThreshold) : dynamicSpeechThreshold
        let isSpeechFrame = rms >= requiredSpeechThreshold
        lastObservedRms = rms
        peakObservedRmsInTurn = max(peakObservedRmsInTurn, rms)
        lastDynamicSpeechThreshold = requiredSpeechThreshold
        diagnosticsFrameCounter += 1
        if isSpeechFrame {
            consecutiveSpeechFrames += 1
            if !hasDetectedSpeechInTurn, consecutiveSpeechFrames >= speechStartConsecutiveFrames {
                pushDebugEvent("speech detected")
                hasDetectedSpeechInTurn = true
            }
            if hasDetectedSpeechInTurn {
                speechFramesInTurn += 1
                peakSpeechRmsInTurn = max(peakSpeechRmsInTurn, rms)
                lastSpeechAt = now
                trailingSilenceFramesRemaining = trailingSilenceFrames
            }
        } else if hasDetectedSpeechInTurn, trailingSilenceFramesRemaining > 0 {
            consecutiveSpeechFrames = 0
            trailingSilenceFramesRemaining -= 1
        } else {
            consecutiveSpeechFrames = 0
        }
        sendAudioFrame(frameB64)
        if diagnosticsFrameCounter == 1 || diagnosticsFrameCounter % 24 == 0 {
            liveVoiceLogger.debug(
                "Audio diagnostics | frame=\(self.diagnosticsFrameCounter) rms=\(rms, privacy: .public) threshold=\(requiredSpeechThreshold, privacy: .public) speechFrame=\(isSpeechFrame) detectedSpeech=\(self.hasDetectedSpeechInTurn) speechFrames=\(self.speechFramesInTurn) transcriptActivity=\(self.hasTranscriptActivityInTurn)"
            )
        }

        guard autoTurnsEnabled else { return }
        let hasTranscriptSignal = hasTranscriptActivityInTurn && peakObservedRmsInTurn >= minimumTranscriptRmsSignal
        guard hasDetectedSpeechInTurn || hasTranscriptSignal else { return }
        guard !isAutoCommittingTurn else { return }

        if let lastSpeechAt, now.timeIntervalSince(lastSpeechAt) >= silenceAutoCommitSeconds {
            pushDebugEvent("auto-commit (silence)")
            await stopListening(reason: "auto_silence")
            return
        }
        if let listeningStartedAt, now.timeIntervalSince(listeningStartedAt) >= maxTurnDurationSeconds {
            pushDebugEvent("auto-commit (max duration)")
            await stopListening(reason: "auto_max_duration")
        }
    }

    private func handleEvent(_ event: VoiceServerEvent) {
        debugLastServerEvent = event.type
        if let turnId = event.turnId {
            debugCurrentTurnId = turnId
        }
        if event.type != "transcript.partial" {
            pushDebugEvent("server -> \(event.type)")
        }
        switch event.type {
        case "session.ready":
            didReceiveSessionReady = true
            statusMessage = "Session ready"
            chatSessionId = event.chatSessionId ?? chatSessionId
            refreshDebugPhase()
            maybeAutoStartListening(reason: "session.ready")
        case "transcript.partial":
            transcriptPartial = event.text ?? ""
            if isListening {
                hasTranscriptActivityInTurn = true
                if hasDetectedSpeechInTurn || peakObservedRmsInTurn >= minimumTranscriptRmsSignal {
                    hasDetectedSpeechInTurn = true
                    lastSpeechAt = Date()
                }
            }
        case "transcript.final":
            transcriptFinal = event.text ?? ""
            transcriptPartial = ""
            setAwaitingAssistant(true, reason: "transcript finalized")
            refreshDebugPhase()
        case "assistant.text.delta":
            assistantText += event.text ?? ""
            isAssistantSpeaking = true
            setAwaitingAssistant(false, reason: "assistant text streaming")
            refreshDebugPhase()
        case "assistant.text.final":
            if let finalText = event.text, !finalText.isEmpty {
                assistantText = finalText
            }
            refreshDebugPhase()
        case "assistant.audio.chunk":
            if let audioB64 = event.audioB64 {
                playbackEngine.enqueuePCM16Base64(audioB64)
                isAssistantSpeaking = true
                setAwaitingAssistant(false, reason: "assistant audio streaming")
                refreshDebugPhase()
                if pendingIntroAck, event.turnId == introTurnId {
                    introHadAudio = true
                }
            }
        case "assistant.audio.final":
            isAssistantSpeaking = false
            statusMessage = "Connected"
            setAwaitingAssistant(false, reason: "assistant audio complete")
            refreshDebugPhase()
            if pendingIntroAck, event.turnId == introTurnId {
                Task { await sendIntroAck() }
            }
        case "turn.completed":
            statusMessage = "Connected"
            setAwaitingAssistant(false, reason: "turn completed")
            refreshDebugPhase()
            if pendingIntroAck, event.turnId == introTurnId, !introHadAudio {
                Task { await sendIntroAck() }
            }
            maybeAutoStartListening(reason: "turn.completed")
        case "turn.cancelled":
            statusMessage = "Cancelled"
            isAssistantSpeaking = false
            setAwaitingAssistant(false, reason: "turn cancelled")
            refreshDebugPhase()
        case "error":
            let message = event.message ?? "Voice error"
            statusMessage = message
            setAwaitingAssistant(false, reason: "server error")
            refreshDebugPhase()
            liveVoiceLogger.error(
                "Voice event error | retryable=\(event.retryable ?? false) code=\(event.code ?? "unknown", privacy: .public) message=\(message, privacy: .public)"
            )
            if event.retryable == true {
                isListening = false
                isAssistantSpeaking = false
                if event.code == "empty_transcript", autoTurnsEnabled {
                    statusMessage = "Didn't catch that. Keep talking."
                    autoResumeListening(reason: "empty transcript")
                }
                refreshDebugPhase()
                return
            }
            connectionState = .failed(message)
            refreshDebugPhase()
        default:
            break
        }
    }

    private func handleRawEvent(_ payload: [String: Any]) {
        guard let type = payload["type"] as? String else { return }
        if type == "turn.started" {
            assistantText = ""
            currentTurnId = payload["turn_id"] as? String
            debugCurrentTurnId = currentTurnId
            let isIntro = (payload["is_intro"] as? Bool) ?? false
            if isIntro {
                introTurnId = currentTurnId
                introHadAudio = false
                pendingIntroAck = true
            } else if !isListening {
                setAwaitingAssistant(true, reason: "turn started")
                refreshDebugPhase()
            }
        }
    }

    private func sendAudioFrame(_ frameB64: String) {
        guard case .connected = connectionState else { return }
        guard isListening else { return }
        let sequence = frameSequence
        frameSequence += 1
        currentTurnFrameCount += 1
        pendingAudioFrameSends += 1

        let payload: [String: Any] = [
            "type": "audio.frame",
            "seq": sequence,
            "pcm16_b64": frameB64,
            "sample_rate_hz": 16_000,
            "channels": 1
        ]
        let previousSend = audioFrameSendChain
        audioFrameSendChain = Task { @MainActor [weak self] in
            _ = await previousSend?.result
            guard let self else { return }
            defer { self.pendingAudioFrameSends = max(0, self.pendingAudioFrameSends - 1) }
            do {
                try await self.sendJSON(payload)
            } catch {
                self.statusMessage = error.localizedDescription
                self.connectionState = .failed(error.localizedDescription)
                self.setAwaitingAssistant(false, reason: "audio frame send failed")
                self.refreshDebugPhase()
                self.pushDebugEvent("audio frame send failed: \(error.localizedDescription)")
            }
        }
    }

    private func sendIntroAck() async {
        pendingIntroAck = false
        introTurnId = nil
        introHadAudio = false
        refreshDebugPhase()
        do {
            try await sendJSON(["type": "intro.ack"])
        } catch {
            liveVoiceLogger.debug("intro.ack send failed: \(error.localizedDescription, privacy: .public)")
        }
    }

    private func sendJSON(_ payload: [String: Any]) async throws {
        if let type = payload["type"] as? String, type != "audio.frame" {
            debugLastClientAction = type
            pushDebugEvent("client -> \(type)")
        }
        try await websocketClient.sendJSON(payload)
    }

    private func maybeAutoStartListening(reason: String) {
        guard case .connected = connectionState else { return }
        guard !isListening else { return }
        guard !isAssistantSpeaking else { return }
        guard !pendingIntroAck else { return }

        let shouldStart: Bool
        if reason == "session.ready" {
            shouldStart = didReceiveSessionReady && shouldAutoStartListeningOnReady
            if shouldStart {
                shouldAutoStartListeningOnReady = false
            }
        } else if reason == "turn.completed" {
            shouldStart = autoTurnsEnabled || shouldAutoStartListeningAfterTurn
            shouldAutoStartListeningAfterTurn = false
        } else {
            shouldStart = false
        }

        if !shouldStart {
            return
        }

        liveVoiceLogger.info("Auto-start listening | reason=\(reason, privacy: .public)")
        pushDebugEvent("auto-start listening (\(reason))")
        Task {
            await startListening()
        }
    }

    private func autoResumeListening(reason: String) {
        guard autoTurnsEnabled else { return }
        guard case .connected = connectionState else { return }
        guard !isListening else { return }
        guard !isAwaitingAssistant else { return }
        guard !isAssistantSpeaking else { return }
        pushDebugEvent("auto-resume listening (\(reason))")
        Task {
            await startListening()
        }
    }

    private func setAwaitingAssistant(_ awaiting: Bool, reason: String) {
        guard isAwaitingAssistant != awaiting else { return }
        isAwaitingAssistant = awaiting
        pushDebugEvent(awaiting ? "waiting: \(reason)" : "ready: \(reason)")
    }

    private func refreshDebugPhase() {
        let nextPhase: String
        switch connectionState {
        case .idle:
            nextPhase = "Idle"
        case .connecting:
            nextPhase = "Connecting"
        case .failed:
            nextPhase = "Failed"
        case .connected:
            if isListening {
                nextPhase = "Listening"
            } else if isAwaitingAssistant {
                nextPhase = "Waiting for response"
            } else if isAssistantSpeaking {
                nextPhase = "Assistant responding"
            } else {
                nextPhase = "Ready"
            }
        }

        if debugPhase != nextPhase {
            debugPhase = nextPhase
            pushDebugEvent("phase -> \(nextPhase)")
        }
    }

    private func pushDebugEvent(_ message: String) {
        #if DEBUG
        let timestamp = Self.debugTimeFormatter.string(from: Date())
        let line = "\(timestamp) \(message)"
        debugEventTimeline.append(line)
        if debugEventTimeline.count > 36 {
            debugEventTimeline.removeFirst(debugEventTimeline.count - 36)
        }
        #endif
    }

    private func reconnectCurrentSession() async {
        guard let currentSessionId = sessionId else {
            connectionState = .failed("Connection lost. Tap Connect to start again.")
            return
        }
        guard !isAutoReconnecting else { return }
        isAutoReconnecting = true
        defer { isAutoReconnecting = false }

        captureEngine.stopCapture()
        isListening = false
        isAssistantSpeaking = false
        pendingAudioFrameSends = 0
        setAwaitingAssistant(false, reason: "reconnecting")
        refreshDebugPhase()
        pushDebugEvent("auto-reconnect attempt")

        do {
            let token = try await sessionService.fetchAccessToken()
            let launchMode = currentRoute?.launchMode ?? .general
            let sourceSurface = currentRoute?.sourceSurface ?? .knowledgeLive
            didReceiveSessionReady = false
            let request = VoiceCreateSessionRequest(
                sessionId: currentSessionId,
                sampleRateHz: 16_000,
                contentId: currentRoute?.contentId,
                chatSessionId: chatSessionId,
                launchMode: launchMode,
                sourceSurface: sourceSurface,
                requestIntro: false
            )
            let sessionResponse = try await sessionService.createSession(request)
            let wsURL = try sessionService.resolveWebSocketURL(path: sessionResponse.websocketPath)
            websocketClient.connect(url: wsURL, bearerToken: token)
            try await sendJSON(
                [
                    "type": "session.start",
                    "session_id": sessionResponse.sessionId
                ]
            )
            connectionState = .connected
            statusMessage = "Reconnected"
            maybeAutoStartListening(reason: "session.ready")
            refreshDebugPhase()
            pushDebugEvent("auto-reconnect success")
            liveVoiceLogger.info(
                "Live voice auto-reconnected | sessionId=\(sessionResponse.sessionId, privacy: .public)"
            )
        } catch {
            connectionState = .failed("Connection lost. Tap Connect to retry.")
            statusMessage = error.localizedDescription
            setAwaitingAssistant(false, reason: "reconnect failed")
            refreshDebugPhase()
            pushDebugEvent("auto-reconnect failed: \(error.localizedDescription)")
            liveVoiceLogger.error(
                "Auto-reconnect failed: \(error.localizedDescription, privacy: .public)"
            )
        }
    }
}
