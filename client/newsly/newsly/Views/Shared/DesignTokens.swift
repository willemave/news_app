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
    /// Default horizontal padding for rows and screen content (20pt baseline).
    static let screenHorizontal: CGFloat = 20
    static let rowHorizontal: CGFloat = 20
    static let rowVertical: CGFloat = 12
    static let sectionTop: CGFloat = 24
    static let sectionBottom: CGFloat = 8
    static let iconSize: CGFloat = 28
    static let smallIcon: CGFloat = 20

    /// Leading inset for row dividers (aligns with text after icon + spacing).
    static let rowDividerInset: CGFloat = rowHorizontal + iconSize + 12
}

// MARK: - Row Metrics

/// Two row families: compact (settings/menus) and regular (content cards).
enum RowMetrics {
    /// Compact rows: settings, menu items, simple navigation (44pt).
    static let compactHeight: CGFloat = 44
    /// Regular rows: content cards, rich list items (76pt).
    static let regularHeight: CGFloat = 76
    /// Thumbnail size for regular rows.
    static let thumbnailSize: CGFloat = 60
    /// Small thumbnail/icon container for compact rows.
    static let smallThumbnailSize: CGFloat = 40
}

// MARK: - Row Family

enum AppRowFamily {
    case compact
    case regular
}

// MARK: - View Modifiers

extension View {
    /// Apply standard row padding and minimum height for a given row family.
    func appRow(_ family: AppRowFamily = .regular) -> some View {
        self
            .padding(.horizontal, Spacing.rowHorizontal)
            .padding(.vertical, Spacing.rowVertical)
            .frame(
                minHeight: family == .compact
                    ? RowMetrics.compactHeight
                    : RowMetrics.regularHeight,
                alignment: .center
            )
            .contentShape(Rectangle())
    }

    /// Standard List row configuration: zero insets (let the row handle padding),
    /// hidden separators, and clear background.
    func appListRow() -> some View {
        self
            .listRowInsets(EdgeInsets())
            .listRowSeparator(.hidden)
            .listRowBackground(Color.clear)
    }

    /// Apply standard screen-level background.
    func screenContainer() -> some View {
        self.background(Color.surfacePrimary)
    }
}
