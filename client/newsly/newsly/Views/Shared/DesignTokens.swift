//
//  DesignTokens.swift
//  newsly
//
//  Design system tokens for consistent styling across the app.
//

import SwiftUI
import UIKit

// MARK: - Colors

extension Color {
    // Surface colors — ascending elevation: primary (page) → secondary (cards) → tertiary (nested)
    static var surfacePrimary: Color {
        Color(UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? UIColor(red: 0.055, green: 0.055, blue: 0.063, alpha: 1.0)  // #0E0E10
                : UIColor(red: 0.929, green: 0.929, blue: 0.941, alpha: 1.0)  // #EDEDF0
        })
    }
    static var surfaceSecondary: Color {
        Color(UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? UIColor(red: 0.086, green: 0.086, blue: 0.098, alpha: 1.0)  // #161619
                : UIColor(red: 0.969, green: 0.969, blue: 0.976, alpha: 1.0)  // #F7F7F9
        })
    }
    static var surfaceTertiary: Color {
        Color(UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? UIColor(red: 0.133, green: 0.133, blue: 0.145, alpha: 1.0)  // #222225
                : UIColor(red: 1.0, green: 1.0, blue: 1.0, alpha: 1.0)        // #FFFFFF
        })
    }

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

    // Editorial colors (Discovery redesign)
    static var editorialText: Color { Color(red: 0.067, green: 0.067, blue: 0.067) }     // #111111
    static var editorialSub: Color { Color(red: 0.443, green: 0.443, blue: 0.478) }      // #71717a
    static var editorialBorder: Color { Color(.systemGray5) }

    // Adaptive accent (topic badges, favorites)
    static var topicAccent: Color {
        Color(UIColor { traitCollection in
            traitCollection.userInterfaceStyle == .dark
                ? UIColor(red: 0.40, green: 0.61, blue: 1.0, alpha: 1.0)   // #669CFF brighter for dark
                : UIColor(red: 0.067, green: 0.322, blue: 0.831, alpha: 1.0) // #1152d4 original for light
        })
    }

    // Platform label color (news feed metadata — muted blue, related to topicAccent family)
    static var platformLabel: Color {
        Color(UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? UIColor(red: 0.55, green: 0.70, blue: 0.95, alpha: 1.0)  // #8CB3F2
                : UIColor(red: 0.20, green: 0.40, blue: 0.70, alpha: 1.0)  // #3366B3
        })
    }

    // Day section delimiter text (distinct grey, not textTertiary)
    static var sectionDelimiter: Color {
        Color(UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? UIColor(red: 0.50, green: 0.50, blue: 0.53, alpha: 1.0)  // #808087
                : UIColor(red: 0.45, green: 0.45, blue: 0.48, alpha: 1.0)  // #73737A
        })
    }

    // Earthy palette (Live Voice)
    static var earthTerracotta: Color { Color(red: 0.765, green: 0.420, blue: 0.310) }  // #C36B4F
    static var earthSage: Color { Color(red: 0.541, green: 0.604, blue: 0.357) }         // #8A9A5B
    static var earthIvory: Color { Color(red: 0.976, green: 0.969, blue: 0.949) }         // #F9F7F2
    static var earthClayMuted: Color { Color(red: 0.898, green: 0.827, blue: 0.773) }     // #E5D3C5
    static var earthStoneDark: Color { Color(red: 0.365, green: 0.341, blue: 0.322) }     // #5D5752
    static var earthWoodWarm: Color { Color(red: 0.545, green: 0.369, blue: 0.235) }      // #8B5E3C

    // Watercolor palette (Landing & Onboarding)
    static var watercolorBase: Color { Color(red: 0.973, green: 0.980, blue: 0.988) }           // #f8fafc
    static var watercolorMistyBlue: Color { Color(red: 0.580, green: 0.680, blue: 0.820) }      // #94ADD1
    static var watercolorDiffusedPeach: Color { Color(red: 0.960, green: 0.620, blue: 0.580) }   // #F59E94
    static var watercolorPaleEmerald: Color { Color(red: 0.400, green: 0.820, blue: 0.640) }     // #66D1A3
    static var watercolorSoftSky: Color { Color(red: 0.500, green: 0.780, blue: 0.960) }         // #80C7F5
    static var watercolorSlate: Color { Color(red: 0.200, green: 0.255, blue: 0.333) }           // #334155
}

// MARK: - Typography

extension Font {
    static let listTitle = Font.body.weight(.medium)
    static let listSubtitle = Font.subheadline
    static let listCaption = Font.caption
    static let listMono = Font.system(.caption, design: .monospaced)

    static let sectionHeader = Font.footnote.weight(.semibold)
    static let chipLabel = Font.caption2.weight(.medium)

    // Feed card typography
    static let feedMeta = Font.system(size: 11, weight: .medium)
    static let feedHeadline = Font.system(size: 18, weight: .semibold)
    static let feedSnippet = Font.system(size: 13)
    static let cardHeadline = Font.system(size: 22, weight: .bold)
    static let cardDescription = Font.system(size: 14)
    static let cardBadge = Font.system(size: 10, weight: .semibold)
    static let cardFooter = Font.system(size: 11, weight: .medium)

    // Editorial typography (Discovery redesign)
    static let editorialDisplay = Font.system(size: 34, weight: .regular, design: .serif)
    static let editorialHeadline = Font.system(size: 22, weight: .regular, design: .serif)
    static let editorialBody = Font.system(size: 15, weight: .regular, design: .serif)
    static let editorialMeta = Font.system(size: 10, weight: .bold)
    static let editorialSubMeta = Font.system(size: 10, weight: .regular)

    // Watercolor typography (Landing & Onboarding)
    static let watercolorDisplay = Font.system(size: 54, weight: .regular, design: .serif)
    static let watercolorSubtitle = Font.system(size: 17, weight: .light)
}

// MARK: - Card Metrics

enum CardMetrics {
    static let heroImageHeight: CGFloat = 180
    static let cardCornerRadius: CGFloat = 8
    static let cardSpacing: CGFloat = 20
    static let textOverlapOffset: CGFloat = -40
}

// MARK: - Text Size

enum AppTextSize: Int, CaseIterable {
    case small = 0
    case standard = 1
    case large = 2
    case extraLarge = 3

    var label: String {
        switch self {
        case .small: return "Small"
        case .standard: return "Standard"
        case .large: return "Large"
        case .extraLarge: return "Extra Large"
        }
    }

    var dynamicTypeSize: DynamicTypeSize {
        switch self {
        case .small: return .small
        case .standard: return .large
        case .large: return .xLarge
        case .extraLarge: return .xxLarge
        }
    }

    init(index: Int) {
        self = AppTextSize(rawValue: index) ?? .standard
    }
}

enum ContentTextSize: Int, CaseIterable {
    case small = 0
    case standard = 1
    case medium = 2
    case large = 3
    case extraLarge = 4

    var label: String {
        switch self {
        case .small: return "Small"
        case .standard: return "Standard"
        case .medium: return "Medium"
        case .large: return "Large"
        case .extraLarge: return "Extra Large"
        }
    }

    var dynamicTypeSize: DynamicTypeSize {
        switch self {
        case .small: return .small
        case .standard: return .large
        case .medium: return .xLarge
        case .large: return .xxLarge
        case .extraLarge: return .xxxLarge
        }
    }

    init(index: Int) {
        self = ContentTextSize(rawValue: index) ?? .medium
    }
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
