//
//  LiveVoiceIdleView.swift
//  newsly
//

import SwiftUI

struct LiveVoiceIdleView: View {
    let connectionState: LiveVoiceViewModel.ConnectionState
    let statusMessage: String
    let onConnect: () -> Void

    @State private var isPressed = false

    private var isConnecting: Bool {
        connectionState == .connecting
    }

    private var errorMessage: String? {
        if case .failed(let msg) = connectionState { return msg }
        return nil
    }

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            micButton
                .padding(.bottom, 32)

            statusLabel

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Neumorphic Mic Button

    private var micButton: some View {
        Button(action: onConnect) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.earthIvory, Color.earthClayMuted.opacity(0.6)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 128, height: 128)
                    .shadow(color: Color.earthStoneDark.opacity(0.25), radius: 12, x: 8, y: 8)
                    .shadow(color: Color.white.opacity(0.8), radius: 12, x: -8, y: -8)

                if isConnecting {
                    ProgressView()
                        .tint(.earthStoneDark)
                } else {
                    Image(systemName: "mic.fill")
                        .font(.system(size: 36, weight: .medium))
                        .foregroundColor(.earthStoneDark)
                }
            }
        }
        .disabled(isConnecting)
        .scaleEffect(isPressed ? 0.92 : 1.0)
        .animation(.easeInOut(duration: 0.15), value: isPressed)
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in isPressed = true }
                .onEnded { _ in isPressed = false }
        )
        .accessibilityIdentifier("live.connect")
        .accessibilityLabel(isConnecting ? "Connecting" : "Connect to Live Voice")
    }

    // MARK: - Status Label

    private var statusLabel: some View {
        VStack(spacing: 8) {
            if let error = errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.earthTerracotta)
                    .multilineTextAlignment(.center)
                    .padding(.bottom, 4)
            }

            HStack(spacing: 6) {
                if isConnecting {
                    ProgressView()
                        .scaleEffect(0.6)
                        .tint(.earthTerracotta)
                } else {
                    Circle()
                        .fill(Color.earthTerracotta)
                        .frame(width: 6, height: 6)
                }

                Text(isConnecting ? "CONNECTING..." : "TAP TO CONNECT")
                    .font(.system(size: 11, weight: .medium))
                    .tracking(2.5)
                    .foregroundColor(.earthStoneDark.opacity(0.6))
            }
        }
        .accessibilityIdentifier("live.status")
    }
}
