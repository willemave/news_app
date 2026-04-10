//
//  HowItWorksModal.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import SwiftUI

struct HowItWorksModal: View {
    let onDone: () -> Void

    @State private var appeared = false

    private let features: [(icon: String, title: String, detail: String)] = [
        ("newspaper.fill", "Read", "Summaries and long-form in one place."),
        ("square.and.arrow.up.fill", "Share", "Send clean AI summaries to anyone."),
        ("brain.head.profile.fill", "Go deeper", "Ask questions, explore key points."),
        ("bubble.left.and.bubble.right.fill", "Discuss", "Jump into Reddit and HN threads.")
    ]

    var body: some View {
        ZStack {
            WatercolorBackground(energy: 0.08)

            VStack(spacing: 0) {
                Spacer()

                // Brand heading
                VStack(spacing: 12) {
                    Text("Welcome to")
                        .font(.watercolorSubtitle)
                        .foregroundColor(.watercolorSlate.opacity(0.5))
                        .opacity(appeared ? 1 : 0)
                        .offset(y: appeared ? 0 : 10)

                    Text("Newsly")
                        .font(.watercolorDisplay)
                        .foregroundColor(.watercolorSlate)
                        .opacity(appeared ? 1 : 0)
                        .offset(y: appeared ? 0 : 12)
                }
                .padding(.bottom, 48)

                // Feature cards
                VStack(spacing: 10) {
                    ForEach(Array(features.enumerated()), id: \.offset) { index, feature in
                        featureRow(icon: feature.icon, title: feature.title, detail: feature.detail)
                            .opacity(appeared ? 1 : 0)
                            .offset(y: appeared ? 0 : 16)
                            .animation(
                                .easeOut(duration: 0.5).delay(0.15 + Double(index) * 0.08),
                                value: appeared
                            )
                    }
                }
                .padding(.horizontal, 24)

                Spacer()

                // CTA
                Button(action: onDone) {
                    Text("Get started")
                        .font(.callout.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .foregroundColor(.white)
                        .background(Color.watercolorSlate)
                        .clipShape(RoundedRectangle(cornerRadius: 24))
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 24)
                .padding(.bottom, 16)
                .opacity(appeared ? 1 : 0)
                .animation(.easeOut(duration: 0.4).delay(0.6), value: appeared)
                .accessibilityIdentifier("onboarding.tutorial.complete")
            }
        }
        .preferredColorScheme(.light)
        .onAppear {
            withAnimation(.easeOut(duration: 0.6)) {
                appeared = true
            }
        }
        .accessibilityIdentifier("onboarding.tutorial.screen")
    }

    private func featureRow(icon: String, title: String, detail: String) -> some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.body.weight(.medium))
                .foregroundColor(.watercolorSlate)
                .frame(width: 40, height: 40)
                .background(Color.white.opacity(0.5))
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.callout.weight(.semibold))
                    .foregroundColor(.watercolorSlate)
                Text(detail)
                    .font(.caption)
                    .foregroundColor(.watercolorSlate.opacity(0.55))
            }

            Spacer()
        }
        .padding(14)
        .background(Color.white.opacity(0.4))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}
