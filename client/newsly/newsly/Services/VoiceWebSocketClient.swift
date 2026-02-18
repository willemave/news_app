//
//  VoiceWebSocketClient.swift
//  newsly
//

import Foundation
import os.log

enum VoiceWebSocketClientError: LocalizedError {
    case notConnected
    case invalidPayload

    var errorDescription: String? {
        switch self {
        case .notConnected:
            return "Live voice websocket is not connected."
        case .invalidPayload:
            return "Invalid websocket payload."
        }
    }
}

final class VoiceWebSocketClient {
    var onEvent: ((VoiceServerEvent) -> Void)?
    var onRawEvent: (([String: Any]) -> Void)?
    var onError: ((String) -> Void)?
    var onDisconnected: (() -> Void)?

    private var task: URLSessionWebSocketTask?
    private var isConnected = false
    private var isIntentionalDisconnect = false
    private var connectionGeneration = 0
    private let logger = Logger(subsystem: "com.newsly", category: "VoiceWebSocketClient")
    private let suppressedPayloadTypes: Set<String> = [
        "audio.frame",
        "transcript.partial",
        "assistant.text.delta",
        "assistant.audio.chunk",
    ]

    func connect(url: URL, bearerToken: String) {
        disconnect()
        isIntentionalDisconnect = false
        connectionGeneration += 1
        let generation = connectionGeneration
        logger.info("Connecting websocket to \(url.absoluteString, privacy: .public)")

        var request = URLRequest(url: url)
        request.setValue("Bearer \(bearerToken)", forHTTPHeaderField: "Authorization")

        let webSocketTask = URLSession.shared.webSocketTask(with: request)
        self.task = webSocketTask
        self.isConnected = true
        webSocketTask.resume()
        logger.info("Websocket task resumed")
        listenForMessages(task: webSocketTask, generation: generation)
    }

    func disconnect() {
        logger.info("Disconnecting websocket")
        isIntentionalDisconnect = true
        connectionGeneration += 1
        isConnected = false
        let closingTask = task
        task = nil
        closingTask?.cancel(with: .normalClosure, reason: nil)
    }

    func sendJSON(_ payload: [String: Any]) async throws {
        guard let task, isConnected else {
            logger.error("sendJSON failed: not connected")
            throw VoiceWebSocketClientError.notConnected
        }
        let data = try JSONSerialization.data(withJSONObject: payload)
        guard let text = String(data: data, encoding: .utf8) else {
            throw VoiceWebSocketClientError.invalidPayload
        }
        if let type = payload["type"] as? String, !suppressedPayloadTypes.contains(type) {
            logger.debug("Sending websocket payload type=\(type, privacy: .public)")
        }
        try await task.send(.string(text))
    }

    private func listenForMessages(task: URLSessionWebSocketTask, generation: Int) {
        guard isConnected else { return }
        task.receive { [weak self] result in
            guard let self else { return }
            guard generation == self.connectionGeneration else { return }
            switch result {
            case .failure(let error):
                if self.isIntentionalDisconnect {
                    return
                }
                self.isConnected = false
                self.logger.error("Websocket receive failed: \(error.localizedDescription, privacy: .public)")
                DispatchQueue.main.async {
                    self.onError?(error.localizedDescription)
                    self.onDisconnected?()
                }
            case .success(let message):
                self.handleMessage(message)
                self.listenForMessages(task: task, generation: generation)
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
              let raw = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            logger.error("Failed to decode websocket message payload")
            return
        }

        let event = try? JSONDecoder().decode(VoiceServerEvent.self, from: data)
        if let type = raw["type"] as? String, !suppressedPayloadTypes.contains(type) {
            logger.debug("Received websocket payload type=\(type, privacy: .public)")
        }
        DispatchQueue.main.async {
            self.onRawEvent?(raw)
            if let event {
                self.onEvent?(event)
            }
        }
    }
}
