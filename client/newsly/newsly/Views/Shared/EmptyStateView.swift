//
//  EmptyStateView.swift
//  newsly
//
//  Centered empty state with icon, title, subtitle, and optional action.
//

import SwiftUI

struct EmptyStateView: View {
    let icon: String
    let title: String
    let subtitle: String
    var actionTitle: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 40, weight: .light))
                .foregroundStyle(Color.textTertiary)

            VStack(spacing: 4) {
                Text(title)
                    .font(.listTitle.weight(.semibold))
                    .foregroundStyle(Color.textPrimary)

                Text(subtitle)
                    .font(.listSubtitle)
                    .foregroundStyle(Color.textSecondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 280)
            }

            if let actionTitle, let action {
                Button(action: action) {
                    Text(actionTitle)
                        .font(.listSubtitle.weight(.medium))
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .padding(.top, 4)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.surfacePrimary)
    }
}

/// Backward-compatible alias.
typealias SettingsEmptyStateView = EmptyStateView

#Preview {
    EmptyStateView(
        icon: "star",
        title: "No Favorites",
        subtitle: "Swipe right on content to save it here",
        actionTitle: "Browse Content",
        action: {}
    )
}
