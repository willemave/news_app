//
//  ChatMarkdownTheme.swift
//  newsly
//
//  Created by Assistant on 2/14/26.
//

import MarkdownUI
import SwiftUI

extension Theme {
    /// A compact markdown theme optimized for chat bubbles.
    /// Based on `.gitHub` but with smaller headings, tighter spacing,
    /// subtle blockquotes, and rounded code blocks.
    static let chat = Theme()
        // MARK: - Text styles
        .text {
            ForegroundColor(.primary)
            FontSize(.em(1.0))
        }
        .link {
            ForegroundColor(Color(UIColor.link))
        }
        .strong {
            FontWeight(.semibold)
        }
        .code {
            FontFamilyVariant(.monospaced)
            FontSize(.em(0.88))
            BackgroundColor(Color(light: Color(.sRGB, red: 0.95, green: 0.96, blue: 0.97), dark: Color(.sRGB, red: 0.2, green: 0.21, blue: 0.23)))
        }

        // MARK: - Headings (compact for chat)
        .heading1 { configuration in
            configuration.label
                .markdownMargin(top: 16, bottom: 8)
                .markdownTextStyle {
                    FontWeight(.bold)
                    FontSize(.em(1.25))
                }
        }
        .heading2 { configuration in
            configuration.label
                .markdownMargin(top: 14, bottom: 6)
                .markdownTextStyle {
                    FontWeight(.semibold)
                    FontSize(.em(1.15))
                }
        }
        .heading3 { configuration in
            configuration.label
                .markdownMargin(top: 12, bottom: 6)
                .markdownTextStyle {
                    FontWeight(.semibold)
                    FontSize(.em(1.05))
                }
        }
        .heading4 { configuration in
            configuration.label
                .markdownMargin(top: 10, bottom: 4)
                .markdownTextStyle {
                    FontWeight(.semibold)
                    FontSize(.em(1.0))
                }
        }
        .heading5 { configuration in
            configuration.label
                .markdownMargin(top: 10, bottom: 4)
                .markdownTextStyle {
                    FontWeight(.semibold)
                    FontSize(.em(0.9))
                }
        }
        .heading6 { configuration in
            configuration.label
                .markdownMargin(top: 10, bottom: 4)
                .markdownTextStyle {
                    FontWeight(.semibold)
                    FontSize(.em(0.85))
                    ForegroundColor(.secondary)
                }
        }

        // MARK: - Paragraph
        .paragraph { configuration in
            configuration.label
                .markdownMargin(top: 0, bottom: 16)
        }

        // MARK: - Blockquote (subtle)
        .blockquote { configuration in
            HStack(spacing: 0) {
                RoundedRectangle(cornerRadius: 1.5)
                    .fill(Color(light: Color(UIColor.systemGray4), dark: Color(UIColor.systemGray3)))
                    .frame(width: 3)
                configuration.label
                    .markdownTextStyle {
                        ForegroundColor(.secondary)
                        FontStyle(.italic)
                    }
                    .padding(.leading, 10)
            }
            .markdownMargin(top: 4, bottom: 12)
        }

        // MARK: - Code block (rounded)
        .codeBlock { configuration in
            ScrollView(.horizontal) {
                configuration.label
                    .markdownTextStyle {
                        FontFamilyVariant(.monospaced)
                        FontSize(.em(0.85))
                    }
            }
            .padding(12)
            .background(Color(light: Color(.sRGB, red: 0.95, green: 0.96, blue: 0.97), dark: Color(.sRGB, red: 0.14, green: 0.15, blue: 0.17)))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .markdownMargin(top: 4, bottom: 12)
        }

        // MARK: - Lists
        .listItem { configuration in
            configuration.label
                .markdownMargin(top: 3, bottom: 3)
        }

        // MARK: - Thematic break
        .thematicBreak {
            Divider()
                .markdownMargin(top: 12, bottom: 12)
        }

        // MARK: - Table
        .table { configuration in
            configuration.label
                .markdownTableBorderStyle(.init(color: .secondary.opacity(0.3)))
                .markdownMargin(top: 4, bottom: 8)
        }
        .tableCell { configuration in
            configuration.label
                .markdownMargin(top: 4, bottom: 4)
                .padding(.horizontal, 8)
        }

        // MARK: - Image
        .image { configuration in
            configuration.label
                .markdownMargin(top: 4, bottom: 8)
        }
}
