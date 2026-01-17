//
//  HowItWorksModal.swift
//  newsly
//
//  Created by Assistant on 1/17/26.
//

import SwiftUI

struct HowItWorksModal: View {
    let onDone: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("How Newsly works")
                .font(.title2.bold())

            VStack(alignment: .leading, spacing: 12) {
                HowItWorksRow(icon: "doc.text", title: "Read articles", detail: "Scan short news or dive into long-form.")
                HowItWorksRow(icon: "square.and.arrow.up", title: "Share an LLM summary", detail: "Send a clean summary to friends.")
                HowItWorksRow(icon: "brain.head.profile", title: "Chat or go deeper", detail: "Ask questions and explore key points.")
                HowItWorksRow(icon: "bubble.left.and.bubble.right", title: "Join the discussion", detail: "Jump to Reddit or Hacker News threads.")
            }

            Spacer()

            Button("Got it") {
                onDone()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(32)
    }
}

private struct HowItWorksRow: View {
    let icon: String
    let title: String
    let detail: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(.blue)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                Text(detail)
                    .font(.footnote)
                    .foregroundColor(.secondary)
            }
        }
    }
}
