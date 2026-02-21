//
//  OnboardingMicButton.swift
//  newsly
//

import SwiftUI

struct OnboardingMicButton: View {
    let audioState: OnboardingAudioState
    let durationSeconds: Int
    let onStart: () -> Void
    let onStop: () -> Void

    @State private var isPressed = false
    @State private var pulseScale: CGFloat = 1.0

    var body: some View {
        VStack(spacing: 28) {
            micButton
            statusLabel
        }
    }

    // MARK: - Neumorphic Mic Button

    private var micButton: some View {
        Button(action: handleTap) {
            ZStack {
                // Pulsing ring for recording
                if audioState == .recording {
                    Circle()
                        .stroke(Color.watercolorDiffusedPeach.opacity(0.5), lineWidth: 3)
                        .frame(width: 144, height: 144)
                        .scaleEffect(pulseScale)
                        .opacity(2.0 - Double(pulseScale))
                        .onAppear {
                            withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                                pulseScale = 1.15
                            }
                        }
                        .onDisappear { pulseScale = 1.0 }
                }

                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.watercolorBase, Color.watercolorMistyBlue.opacity(0.4)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 128, height: 128)
                    .shadow(color: Color.watercolorSlate.opacity(0.2), radius: 12, x: 8, y: 8)
                    .shadow(color: Color.white.opacity(0.8), radius: 12, x: -8, y: -8)

                iconContent
            }
        }
        .disabled(audioState == .transcribing)
        .scaleEffect(isPressed ? 0.92 : 1.0)
        .animation(.easeInOut(duration: 0.15), value: isPressed)
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in isPressed = true }
                .onEnded { _ in isPressed = false }
        )
        .accessibilityLabel(accessibilityText)
    }

    @ViewBuilder
    private var iconContent: some View {
        switch audioState {
        case .idle, .error:
            Image(systemName: "mic.fill")
                .font(.system(size: 36, weight: .medium))
                .foregroundColor(.watercolorSlate)
        case .recording:
            Image(systemName: "stop.fill")
                .font(.system(size: 30, weight: .medium))
                .foregroundColor(.watercolorDiffusedPeach)
        case .transcribing:
            ProgressView()
                .tint(.watercolorSlate)
        }
    }

    // MARK: - Status Label

    private var statusLabel: some View {
        VStack(spacing: 8) {
            if audioState == .recording {
                Text(formattedDuration)
                    .font(.title3.monospacedDigit())
                    .foregroundColor(.watercolorSlate.opacity(0.6))
            }

            Text(statusText)
                .font(.system(size: 11, weight: .medium))
                .tracking(2.5)
                .foregroundColor(.watercolorSlate.opacity(0.5))
        }
    }

    // MARK: - Helpers

    private var statusText: String {
        switch audioState {
        case .idle: return "TAP TO SPEAK"
        case .recording: return "LISTENING..."
        case .transcribing: return "PROCESSING..."
        case .error: return "TAP TO RETRY"
        }
    }

    private var accessibilityText: String {
        switch audioState {
        case .idle: return "Tap to start recording"
        case .recording: return "Recording. Tap to stop."
        case .transcribing: return "Processing speech"
        case .error: return "Tap to retry recording"
        }
    }

    private var formattedDuration: String {
        let minutes = durationSeconds / 60
        let seconds = durationSeconds % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    private func handleTap() {
        switch audioState {
        case .idle, .error:
            onStart()
        case .recording:
            onStop()
        case .transcribing:
            break
        }
    }
}
