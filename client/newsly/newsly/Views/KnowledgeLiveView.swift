//
//  KnowledgeLiveView.swift
//  newsly
//

import SwiftUI

struct KnowledgeLiveView: View {
    let initialRoute: LiveVoiceRoute?
    let onOpenChatSession: ((Int) -> Void)?

    @Environment(\.colorScheme) private var colorScheme
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
}
