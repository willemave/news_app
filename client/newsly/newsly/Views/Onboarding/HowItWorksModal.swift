//
//  HowItWorksModal.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import SwiftUI

struct HowItWorksModal: View {
    let onDone: () -> Void

    private let features: [(icon: String, color: Color, title: String, detail: String)] = [
        ("newspaper", .accentColor, "Read articles", "Scan short news or dive into long-form."),
        ("square.and.arrow.up", .purple, "Share summaries", "Send a clean AI summary to friends."),
        ("brain.head.profile", .orange, "Chat or go deeper", "Ask questions and explore key points."),
        ("bubble.left.and.bubble.right", .green, "Join discussions", "Jump to Reddit or Hacker News threads.")
    ]

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 28) {
                Text("How Newsly works")
                    .font(.title2.bold())

                VStack(spacing: 16) {
                    ForEach(Array(features.enumerated()), id: \.offset) { _, feature in
                        HStack(spacing: 14) {
                            Image(systemName: feature.icon)
                                .font(.body.weight(.medium))
                                .foregroundColor(feature.color)
                                .frame(width: 36, height: 36)
                                .background(feature.color.opacity(0.1))
                                .clipShape(Circle())

                            VStack(alignment: .leading, spacing: 2) {
                                Text(feature.title)
                                    .font(.callout.weight(.semibold))
                                Text(feature.detail)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                        }
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()

            Button(action: onDone) {
                Text("Got it")
                    .font(.callout.weight(.semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .foregroundColor(.white)
                    .background(Color.accentColor)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 24)
            .padding(.bottom, 16)
        }
    }
}
