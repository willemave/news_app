//
//  DesignTokens.swift
//  newsly
//
//  Design system tokens for consistent styling across the app.
//

import SwiftUI

// MARK: - Colors

extension Color {
    // Surface colors
    static var surfacePrimary: Color { Color(.systemBackground) }
    static var surfaceSecondary: Color { Color(.secondarySystemBackground) }
    static var surfaceTertiary: Color { Color(.tertiarySystemBackground) }

    // Text colors
    static var textPrimary: Color { Color(.label) }
    static var textSecondary: Color { Color(.secondaryLabel) }
    static var textTertiary: Color { Color(.tertiaryLabel) }

    // Border colors
    static var borderSubtle: Color { Color(.separator) }
    static var borderStrong: Color { Color(.opaqueSeparator) }

    // Status colors (Linear-style muted)
    static var statusActive: Color { Color.green.opacity(0.85) }
    static var statusInactive: Color { Color(.tertiaryLabel) }
    static var statusDestructive: Color { Color.red.opacity(0.85) }
}

// MARK: - Typography

extension Font {
    static let listTitle = Font.body.weight(.medium)
    static let listSubtitle = Font.subheadline
    static let listCaption = Font.caption
    static let listMono = Font.system(.caption, design: .monospaced)

    static let sectionHeader = Font.footnote.weight(.semibold)
    static let chipLabel = Font.caption2.weight(.medium)
}

// MARK: - Spacing

enum Spacing {
    static let rowHorizontal: CGFloat = 16
    static let rowVertical: CGFloat = 12
    static let sectionTop: CGFloat = 24
    static let sectionBottom: CGFloat = 8
    static let iconSize: CGFloat = 28
    static let smallIcon: CGFloat = 20
}
