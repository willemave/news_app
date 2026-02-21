//
//  LiveVoiceActiveView.swift
//  newsly
//

import SwiftUI

struct LiveVoiceActiveView: View {
    let sphereEnergy: Float
    let isListening: Bool
    let isAssistantSpeaking: Bool
    let isAwaitingAssistant: Bool
    let statusMessage: String
    let onDisconnect: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            statusPill
                .padding(.top, 60)

            Spacer()

            endButton
                .padding(.bottom, 60)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Status Pill

    private var statusPill: some View {
        HStack(spacing: 8) {
            Image(systemName: "mic.fill")
                .font(.system(size: 10))
                .foregroundColor(.white.opacity(0.8))

            Circle()
                .fill(pillDotColor)
                .frame(width: 6, height: 6)
                .modifier(PulsingDot(isActive: isListening || isAssistantSpeaking))

            Text(pillText)
                .font(.system(size: 11, weight: .medium))
                .tracking(1.5)
                .foregroundColor(.white.opacity(0.9))
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Capsule().fill(.ultraThinMaterial))
        .accessibilityIdentifier("live.status_pill")
    }

    private var pillText: String {
        if isAssistantSpeaking { return "SPEAKING..." }
        if isAwaitingAssistant { return "THINKING..." }
        return "LISTENING..."
    }

    private var pillDotColor: Color {
        if isAssistantSpeaking { return .earthSage }
        if isAwaitingAssistant { return .earthTerracotta.opacity(0.7) }
        return .earthTerracotta
    }

    // MARK: - End Button

    private var endButton: some View {
        VStack(spacing: 10) {
            Button(action: onDisconnect) {
                ZStack {
                    Circle()
                        .fill(Color.white.opacity(0.15))
                        .frame(width: 56, height: 56)

                    Image(systemName: "xmark")
                        .font(.system(size: 20, weight: .medium))
                        .foregroundColor(.white)
                }
            }
            .accessibilityIdentifier("live.end")
            .accessibilityLabel("End Session")

            Text("End Session")
                .font(.system(size: 12, weight: .medium))
                .foregroundColor(.white.opacity(0.6))
        }
    }
}

// MARK: - Pulsing Dot Modifier

private struct PulsingDot: ViewModifier {
    let isActive: Bool
    @State private var isPulsing = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(isPulsing ? 1.4 : 1.0)
            .opacity(isPulsing ? 0.6 : 1.0)
            .animation(
                isActive
                    ? .easeInOut(duration: 0.8).repeatForever(autoreverses: true)
                    : .default,
                value: isPulsing
            )
            .onChange(of: isActive) { _, newValue in
                isPulsing = newValue
            }
            .onAppear {
                isPulsing = isActive
            }
    }
}
