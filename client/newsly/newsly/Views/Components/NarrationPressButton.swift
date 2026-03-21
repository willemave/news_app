//
//  NarrationPressButton.swift
//  newsly
//

import SwiftUI

struct NarrationPressButton<Label: View>: View {
    let isDisabled: Bool
    let accessibilityLabel: String
    let accessibilityHint: String
    let onTap: () -> Void
    let onLongPress: () -> Void
    let label: () -> Label

    init(
        isDisabled: Bool = false,
        accessibilityLabel: String,
        accessibilityHint: String = "Long press to play at 1.5x speed.",
        onTap: @escaping () -> Void,
        onLongPress: @escaping () -> Void,
        @ViewBuilder label: @escaping () -> Label
    ) {
        self.isDisabled = isDisabled
        self.accessibilityLabel = accessibilityLabel
        self.accessibilityHint = accessibilityHint
        self.onTap = onTap
        self.onLongPress = onLongPress
        self.label = label
    }

    var body: some View {
        Group {
            if isDisabled {
                content
                    .opacity(0.6)
            } else {
                content
                    .gesture(
                        LongPressGesture(minimumDuration: 0.4)
                            .exclusively(before: TapGesture())
                            .onEnded(handleGestureEnded)
                    )
            }
        }
    }

    private var content: some View {
        label()
            .contentShape(Rectangle())
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(.isButton)
            .accessibilityLabel(accessibilityLabel)
            .accessibilityHint(accessibilityHint)
            .accessibilityAction {
                guard !isDisabled else { return }
                onTap()
            }
            .accessibilityAction(named: "Play at 1.5x") {
                guard !isDisabled else { return }
                onLongPress()
            }
    }

    private func handleGestureEnded(
        _ value: ExclusiveGesture<LongPressGesture, TapGesture>.Value
    ) {
        switch value {
        case .first(true):
            onLongPress()
        case .second:
            onTap()
        default:
            break
        }
    }
}
