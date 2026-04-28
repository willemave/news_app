//
//  LongformArtifactView.swift
//  newsly
//
//  Renderer for typed long-form artifacts.
//

import SwiftUI

private enum ArtifactDesign {
    static let sectionSpacing: CGFloat = 20
    static let rowSpacing: CGFloat = 10
}

struct LongformArtifactView: View {
    let artifact: LongformArtifactEnvelope
    var contentId: Int?

    var body: some View {
        switch artifact.artifact.type {
        case "argument":
            ArgumentView(artifact: artifact)
        case "mental_model":
            MentalModelView(artifact: artifact)
        case "playbook":
            PlaybookView(artifact: artifact)
        case "portrait":
            PortraitView(artifact: artifact)
        case "briefing":
            BriefingView(artifact: artifact)
        case "walkthrough":
            WalkthroughView(artifact: artifact)
        case "findings":
            FindingsView(artifact: artifact)
        default:
            ArtifactScaffold(artifact: artifact, accent: .blue)
        }
    }
}

struct ArgumentView: View {
    let artifact: LongformArtifactEnvelope

    var body: some View {
        ArtifactScaffold(artifact: artifact, accent: .indigo)
    }
}

struct MentalModelView: View {
    let artifact: LongformArtifactEnvelope

    var body: some View {
        ArtifactScaffold(artifact: artifact, accent: .teal)
    }
}

struct PlaybookView: View {
    let artifact: LongformArtifactEnvelope

    var body: some View {
        ArtifactScaffold(artifact: artifact, accent: .green)
    }
}

struct PortraitView: View {
    let artifact: LongformArtifactEnvelope

    var body: some View {
        ArtifactScaffold(artifact: artifact, accent: .purple)
    }
}

struct BriefingView: View {
    let artifact: LongformArtifactEnvelope

    var body: some View {
        ArtifactScaffold(artifact: artifact, accent: .orange)
    }
}

struct WalkthroughView: View {
    let artifact: LongformArtifactEnvelope

    var body: some View {
        ArtifactScaffold(artifact: artifact, accent: .cyan)
    }
}

struct FindingsView: View {
    let artifact: LongformArtifactEnvelope

    var body: some View {
        ArtifactScaffold(artifact: artifact, accent: .red)
    }
}

private struct ArtifactScaffold: View {
    let artifact: LongformArtifactEnvelope
    let accent: Color

    private var payload: LongformArtifactPayload {
        artifact.artifact.payload
    }

    var body: some View {
        VStack(alignment: .leading, spacing: ArtifactDesign.sectionSpacing) {
            ArtifactHeader(artifact: artifact, accent: accent)
            OverviewBlock(text: payload.overview)

            if !payload.quotes.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    ArtifactSectionHeader("Source Quotes", icon: "quote.opening", tint: accent)
                    ForEach(payload.quotes) { quote in
                        ArtifactQuoteCard(quote: quote, tint: accent)
                    }
                }
            }

            ExtrasPanel(sections: payload.extrasSections, tint: accent)
            KeyPointList(points: payload.keyPoints, tint: accent)
            TakeawayBanner(text: payload.takeaway, tint: accent)
        }
    }
}

private struct ArtifactHeader: View {
    let artifact: LongformArtifactEnvelope
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(artifact.displayType.uppercased())
                .font(.caption)
                .fontWeight(.semibold)
                .tracking(0.6)
                .foregroundStyle(accent)

            Text(artifact.oneLine)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct OverviewBlock: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.callout)
            .foregroundColor(.primary.opacity(0.92))
            .lineSpacing(5)
            .fixedSize(horizontal: false, vertical: true)
    }
}

private struct ExtrasPanel: View {
    let sections: [LongformExtrasSection]
    let tint: Color

    var body: some View {
        if !sections.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                ArtifactSectionHeader("Frame", icon: "square.stack.3d.up", tint: tint)

                VStack(alignment: .leading, spacing: 14) {
                    ForEach(sections) { section in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(section.title)
                                .font(.footnote)
                                .fontWeight(.semibold)
                                .foregroundColor(.secondary)
                                .textCase(.uppercase)
                                .tracking(0.5)

                            ForEach(section.items, id: \.self) { item in
                                ArtifactBulletRow(text: item)
                            }
                        }
                    }
                }
            }
        }
    }
}

private struct KeyPointList: View {
    let points: [LongformArtifactKeyPoint]
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ArtifactSectionHeader("Key Points", icon: "list.bullet.rectangle", tint: tint)

            VStack(alignment: .leading, spacing: 14) {
                ForEach(points) { point in
                    VStack(alignment: .leading, spacing: 5) {
                        Text(point.heading)
                            .font(.callout)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)
                            .fixedSize(horizontal: false, vertical: true)

                        Text(point.content)
                            .font(.callout)
                            .foregroundColor(.primary.opacity(0.88))
                            .lineSpacing(3)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
    }
}

private struct TakeawayBanner: View {
    let text: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ArtifactSectionHeader("Takeaway", icon: "checkmark.seal", tint: tint)
            Text(text)
                .font(.callout)
                .fontWeight(.medium)
                .foregroundStyle(.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.leading, 14)
        .overlay(
            Rectangle()
                .fill(tint.opacity(0.65))
                .frame(width: 3),
            alignment: .leading
        )
    }
}

private struct ArtifactQuoteCard: View {
    let quote: LongformArtifactQuote
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(quote.text)
                .font(.callout)
                .italic()
                .foregroundColor(.primary.opacity(0.9))
                .fixedSize(horizontal: false, vertical: true)

            if let attribution = quote.attribution?.trimmingCharacters(in: .whitespacesAndNewlines),
               !attribution.isEmpty {
                Text("- \(attribution)")
                    .font(.footnote)
                    .fontWeight(.medium)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.leading, 14)
        .overlay(
            Rectangle()
                .fill(tint.opacity(0.55))
                .frame(width: 3),
            alignment: .leading
        )
    }
}

private struct ArtifactBulletRow: View {
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(Color.primary.opacity(0.5))
                .frame(width: 5, height: 5)
                .padding(.top, 7)
            Text(text)
                .font(.callout)
                .foregroundColor(.primary.opacity(0.9))
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct ArtifactSectionHeader: View {
    let title: String
    let icon: String
    let tint: Color

    init(_ title: String, icon: String, tint: Color) {
        self.title = title
        self.icon = icon
        self.tint = tint
    }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.subheadline)
                .foregroundColor(tint)
            Text(title)
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)
                .textCase(.uppercase)
                .tracking(0.5)
        }
    }
}
