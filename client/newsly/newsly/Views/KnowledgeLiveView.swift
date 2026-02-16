//
//  KnowledgeLiveView.swift
//  newsly
//

import SwiftUI

struct KnowledgeLiveView: View {
    let initialRoute: LiveVoiceRoute?
    let onOpenChatSession: ((Int) -> Void)?

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

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                LiveVoiceSphereView(
                    energy: viewModel.sphereEnergy,
                    isSpeaking: viewModel.isAssistantSpeaking,
                    isListening: viewModel.isListening,
                    isThinking: viewModel.isAwaitingAssistant
                )
                .padding(.top, 28)
                .accessibilityIdentifier("live.sphere")

                Text(viewModel.statusMessage)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .accessibilityIdentifier("live.status")

                #if DEBUG
                if settings.showLiveVoiceDebugText {
                    conversationPanel
                    debugStatusPanel
                }
                #endif
                controlsSection

                if let chatSessionId = viewModel.chatSessionId {
                    Button("Open Session in Chats") {
                        onOpenChatSession?(chatSessionId)
                    }
                    .font(.footnote.weight(.semibold))
                    .accessibilityIdentifier("live.open_session")
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 24)
        }
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
        .padding(14)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityIdentifier("live.conversation_panel")
    }

    #if DEBUG
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
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
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
        case .idle:
            return "idle"
        case .connecting:
            return "connecting"
        case .connected:
            return "connected"
        case .failed:
            return "failed"
        }
    }

    private var phaseColor: Color {
        switch viewModel.debugPhase {
        case "Listening":
            return .blue
        case "Waiting for response":
            return .orange
        case "Assistant responding":
            return .green
        case "Failed":
            return .red
        default:
            return .secondary
        }
    }
    #endif

    private var controlsSection: some View {
        VStack(spacing: 10) {
            switch viewModel.connectionState {
            case .idle, .failed:
                Button("Connect") {
                    Task { await viewModel.connect(route: initialRoute) }
                }
                .buttonStyle(.borderedProminent)
                .accessibilityIdentifier("live.connect")
            case .connecting:
                ProgressView("Connecting...")
                    .padding(.vertical, 6)
                    .accessibilityIdentifier("live.connecting")
            case .connected:
                Text(
                    viewModel.isListening
                        ? "Hands-free mode is on. Just talk naturally."
                        : "Preparing microphone..."
                )
                .font(.footnote)
                .foregroundColor(.secondary)
                .accessibilityIdentifier("live.handsfree_hint")

                Button("End") {
                    Task { await viewModel.disconnect() }
                }
                .buttonStyle(.bordered)
                .accessibilityIdentifier("live.end")
            }
        }
        .accessibilityElement(children: .contain)
    }
}
