//
//  SearchBar.swift
//  newsly
//

import SwiftUI

struct SearchBar: View {
    let placeholder: String
    @Binding var text: String
    var isLoading: Bool = false
    var onSubmit: (() -> Void)? = nil
    var onClear: (() -> Void)? = nil

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 16, weight: .regular))
                .foregroundColor(.textSecondary)

            TextField(placeholder, text: $text)
                .font(.system(size: 16))
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.search)
                .onSubmit { onSubmit?() }

            if isLoading {
                ProgressView()
                    .controlSize(.small)
            } else if !text.isEmpty {
                Button {
                    text = ""
                    onClear?()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 16))
                        .foregroundColor(.textSecondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Clear search")
            }
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 14)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.borderStrong, lineWidth: 1)
        )
    }
}
