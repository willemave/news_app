//
//  LiveVoiceSphereView.swift
//  newsly
//

import SwiftUI

struct LiveVoiceSphereView: View {
    let energy: Float
    let isSpeaking: Bool

    @State private var phase: CGFloat = 0

    private var normalizedEnergy: CGFloat {
        CGFloat(min(1, max(0, energy)))
    }

    var body: some View {
        ZStack {
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            Color.cyan.opacity(0.95),
                            Color.blue.opacity(0.55),
                            Color.indigo.opacity(0.2)
                        ],
                        center: .center,
                        startRadius: 10,
                        endRadius: 120
                    )
                )
                .frame(width: 170, height: 170)
                .scaleEffect(1 + normalizedEnergy * 0.18)
                .shadow(color: Color.cyan.opacity(0.45), radius: 22 + normalizedEnergy * 18)

            Circle()
                .stroke(Color.white.opacity(0.25), lineWidth: 1.2)
                .frame(width: 210, height: 210)
                .scaleEffect(1 + normalizedEnergy * 0.22)
                .opacity(isSpeaking ? 0.9 : 0.25)
                .animation(.easeOut(duration: 0.12), value: normalizedEnergy)

            Circle()
                .stroke(Color.cyan.opacity(0.3), lineWidth: 1.4)
                .frame(width: 245, height: 245)
                .scaleEffect(1 + normalizedEnergy * 0.3)
                .opacity(isSpeaking ? 0.75 : 0.2)
                .animation(.easeOut(duration: 0.12), value: normalizedEnergy)
        }
        .rotationEffect(.degrees(Double(phase)))
        .animation(.linear(duration: isSpeaking ? 1.2 : 4.0).repeatForever(autoreverses: false), value: phase)
        .onAppear {
            phase = 360
        }
    }
}
