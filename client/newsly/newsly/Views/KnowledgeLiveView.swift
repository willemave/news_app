//
//  KnowledgeLiveView.swift
//  newsly
//

import SwiftUI

struct KnowledgeLiveView: View {
    let initialRoute: LiveVoiceRoute?
    let onOpenChatSession: ((Int) -> Void)?

    @Environment(\.colorScheme) private var colorScheme
    @ObservedObject private var settings = AppSettings.shared
    @StateObject private var viewModel = LiveVoiceViewModel()
    @State private var hasAutoConnected = false

    init(
        initialRoute: LiveVoiceRoute? = nil,
        onOpenChatSession: ((Int) -> Void)? = nil
    ) {
        self.initialRoute = initialRoute
        self.onOpenChatSession = onOpenChatSession
    }

    private var isActive: Bool {
        viewModel.connectionState == .connected
    }

    var body: some View {
        ZStack {
            // Background layer
            if isActive {
                LiveVoiceAmbientBackground(
                    energy: viewModel.sphereEnergy,
                    isActive: true
                )
            } else {
                idleBackground
            }

            // Content layer
            if isActive {
                activeContent
            } else {
                idleContent
            }

            // Debug overlay
            #if DEBUG
            if settings.showLiveVoiceDebugText {
                debugOverlay
            }
            #endif
        }
        .animation(.easeInOut(duration: 0.6), value: viewModel.connectionState)
        .accessibilityIdentifier("live.screen")
        .task {
            guard initialRoute?.autoConnect == true, !hasAutoConnected else { return }
            hasAutoConnected = true
            await viewModel.connect(route: initialRoute)
        }
        .onDisappear {
            Task { await viewModel.disconnect() }
        }
    }

    // MARK: - Idle Background

    private var idleBackground: some View {
        ZStack {
            Color.earthIvory
            RadialGradient(
                colors: [
                    Color.earthTerracotta.opacity(colorScheme == .dark ? 0.15 : 0.08),
                    Color.clear,
                ],
                center: .center,
                startRadius: 10,
                endRadius: 300
            )
        }
        .ignoresSafeArea()
    }

    // MARK: - Idle Content

    private var idleContent: some View {
        VStack(spacing: 0) {
            LiveVoiceIdleView(
                connectionState: viewModel.connectionState,
                statusMessage: viewModel.statusMessage,
                onConnect: {
                    Task { await viewModel.connect(route: initialRoute) }
                }
            )

            if let chatSessionId = viewModel.chatSessionId {
                sessionButton(chatSessionId: chatSessionId, lightText: false)
                    .padding(.bottom, 24)
            }
        }
    }

    // MARK: - Active Content

    private var activeContent: some View {
        VStack(spacing: 0) {
            LiveVoiceActiveView(
                sphereEnergy: viewModel.sphereEnergy,
                isListening: viewModel.isListening,
                isAssistantSpeaking: viewModel.isAssistantSpeaking,
                isAwaitingAssistant: viewModel.isAwaitingAssistant,
                statusMessage: viewModel.statusMessage,
                onDisconnect: {
                    Task { await viewModel.disconnect() }
                }
            )

            if let chatSessionId = viewModel.chatSessionId {
                sessionButton(chatSessionId: chatSessionId, lightText: true)
                    .padding(.bottom, 16)
            }
        }
    }

    // MARK: - Session Button

    private func sessionButton(chatSessionId: Int, lightText: Bool) -> some View {
        Button("Open Session in Chats") {
            onOpenChatSession?(chatSessionId)
        }
        .font(.footnote.weight(.semibold))
        .foregroundColor(lightText ? .white.opacity(0.7) : .earthStoneDark.opacity(0.7))
        .accessibilityIdentifier("live.open_session")
    }

    // MARK: - Debug Overlay

    #if DEBUG
    private var debugOverlay: some View {
        VStack {
            Spacer()
            VStack(spacing: 8) {
                conversationPanel
                debugStatusPanel
            }
            .padding(12)
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .padding(.horizontal, 16)
            .padding(.bottom, 8)
        }
    }

    private var conversationPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !viewModel.transcriptPartial.isEmpty {
                Text(viewModel.transcriptPartial)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }

            if !viewModel.transcriptFinal.isEmpty {
                Text("You: \(viewModel.transcriptFinal)")
                    .font(.subheadline)
                    .foregroundColor(.primary)
            }

            if !viewModel.assistantText.isEmpty {
                Text("Assistant: \(viewModel.assistantText)")
                    .font(.subheadline)
                    .foregroundColor(.primary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityIdentifier("live.conversation_panel")
    }

    private var debugStatusPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Debug")
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.secondary)
                Spacer()
                Text(viewModel.debugPhase)
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(phaseColor.opacity(0.15))
                    .foregroundColor(phaseColor)
                    .clipShape(Capsule())
            }

            debugRow(label: "Connection", value: connectionLabel)
            debugRow(label: "Awaiting", value: viewModel.isAwaitingAssistant ? "yes" : "no")
            debugRow(label: "Listening", value: viewModel.isListening ? "yes" : "no")
            debugRow(label: "Assistant", value: viewModel.isAssistantSpeaking ? "speaking" : "idle")
            debugRow(label: "Turn", value: viewModel.debugCurrentTurnId ?? "-")
            debugRow(label: "Last server", value: viewModel.debugLastServerEvent)
            debugRow(label: "Last client", value: viewModel.debugLastClientAction)

            if !viewModel.debugEventTimeline.isEmpty {
                Divider()
                    .padding(.vertical, 2)

                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(viewModel.debugEventTimeline.suffix(12).enumerated()), id: \.offset) { _, line in
                        Text(line)
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundColor(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityIdentifier("live.debug_panel")
    }

    private func debugRow(label: String, value: String) -> some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundColor(.secondary)
                .frame(width: 82, alignment: .leading)
            Text(value)
                .font(.caption)
                .foregroundColor(.primary)
                .lineLimit(1)
            Spacer(minLength: 0)
        }
    }

    private var connectionLabel: String {
        switch viewModel.connectionState {
        case .idle: return "idle"
        case .connecting: return "connecting"
        case .connected: return "connected"
        case .failed: return "failed"
        }
    }

    private var phaseColor: Color {
        switch viewModel.debugPhase {
        case "Listening": return .blue
        case "Waiting for response": return .orange
        case "Assistant responding": return .green
        case "Failed": return .red
        default: return .secondary
        }
    }
    #endif
}
