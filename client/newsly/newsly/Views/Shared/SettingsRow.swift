//
//  SettingsRow.swift
//  newsly
//
//  Standard settings row with icon, title, subtitle, and trailing accessory.
//

import SwiftUI

struct SettingsRow<Accessory: View>: View {
    let icon: String
    let iconColor: Color
    let title: String
    var subtitle: String? = nil
    @ViewBuilder var accessory: () -> Accessory

    init(
        icon: String,
        iconColor: Color = .accentColor,
        title: String,
        subtitle: String? = nil,
        @ViewBuilder accessory: @escaping () -> Accessory
    ) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.subtitle = subtitle
        self.accessory = accessory
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 17, weight: .medium))
                .foregroundStyle(iconColor)
                .frame(width: Spacing.iconSize, height: Spacing.iconSize)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.listTitle)
                    .foregroundStyle(Color.textPrimary)

                if let subtitle {
                    Text(subtitle)
                        .font(.listCaption)
                        .foregroundStyle(Color.textTertiary)
                        .lineLimit(1)
                }
            }

            Spacer(minLength: 8)

            accessory()
        }
        .appRow(.compact)
    }
}

// MARK: - Convenience initializer for navigation rows

extension SettingsRow where Accessory == NavigationChevron {
    init(
        icon: String,
        iconColor: Color = .accentColor,
        title: String,
        subtitle: String? = nil
    ) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.subtitle = subtitle
        self.accessory = { NavigationChevron() }
    }
}

// MARK: - Navigation Chevron

struct NavigationChevron: View {
    var body: some View {
        Image(systemName: "chevron.right")
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(Color.textTertiary)
    }
}

// MARK: - Settings Toggle Row

struct SettingsToggleRow: View {
    let icon: String
    let iconColor: Color
    let title: String
    var subtitle: String? = nil
    @Binding var isOn: Bool

    init(
        icon: String,
        iconColor: Color = .accentColor,
        title: String,
        subtitle: String? = nil,
        isOn: Binding<Bool>
    ) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.subtitle = subtitle
        self._isOn = isOn
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 17, weight: .medium))
                .foregroundStyle(iconColor)
                .frame(width: Spacing.iconSize, height: Spacing.iconSize)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.listTitle)
                    .foregroundStyle(Color.textPrimary)

                if let subtitle {
                    Text(subtitle)
                        .font(.listCaption)
                        .foregroundStyle(Color.textTertiary)
                        .lineLimit(2)
                }
            }

            Spacer(minLength: 8)

            Toggle("", isOn: $isOn)
                .labelsHidden()
        }
        .appRow(.compact)
    }
}

#Preview {
    VStack(spacing: 0) {
        SettingsRow(icon: "star", iconColor: .yellow, title: "Favorites")

        RowDivider()

        SettingsRow(icon: "list.bullet.rectangle", title: "Feed Sources", subtitle: "12 sources")

        RowDivider()

        SettingsToggleRow(
            icon: "eye",
            iconColor: .blue,
            title: "Show Read Articles",
            subtitle: "Display both read and unread",
            isOn: .constant(true)
        )
    }
    .background(Color.surfacePrimary)
}
