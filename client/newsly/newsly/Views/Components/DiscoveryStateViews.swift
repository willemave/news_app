//
//  DiscoveryStateViews.swift
//  newsly
//

import SwiftUI

// MARK: - Loading State (Editorial Skeleton)

struct DiscoveryLoadingStateView: View {
    @State private var shimmer = false

    var body: some View {
        VStack(spacing: 12) {
            ForEach(0..<3, id: \.self) { _ in
                skeletonCard
            }
        }
        .padding(.horizontal, Spacing.screenHorizontal)
        .padding(.top, 32)
        .padding(.bottom, 200)
        .onAppear {
            withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                shimmer = true
            }
        }
    }

    private var skeletonCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Metadata bar skeleton
            HStack(spacing: 6) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color(.tertiarySystemFill))
                    .frame(width: 10, height: 10)
                    .opacity(shimmer ? 0.4 : 0.7)

                RoundedRectangle(cornerRadius: 2)
                    .fill(Color(.tertiarySystemFill))
                    .frame(width: 50, height: 8)
                    .opacity(shimmer ? 0.3 : 0.6)

                RoundedRectangle(cornerRadius: 2)
                    .fill(Color(.tertiarySystemFill))
                    .frame(width: 80, height: 8)
                    .opacity(shimmer ? 0.3 : 0.6)

                Spacer()
            }

            // Headline skeleton
            RoundedRectangle(cornerRadius: 4)
                .fill(Color(.tertiarySystemFill))
                .frame(height: 20)
                .frame(maxWidth: .infinity)
                .opacity(shimmer ? 0.4 : 0.8)

            RoundedRectangle(cornerRadius: 4)
                .fill(Color(.tertiarySystemFill))
                .frame(width: 200, height: 20)
                .opacity(shimmer ? 0.3 : 0.7)
        }
        .padding(16)
        .background(Color(.secondarySystemGroupedBackground))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.editorialBorder, lineWidth: 1)
        )
        .cornerRadius(12)
    }
}

// MARK: - Error State

struct DiscoveryErrorStateView: View {
    let error: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 28, weight: .light))
                .foregroundColor(.editorialSub)

            VStack(spacing: 6) {
                Text("Something went wrong")
                    .font(.editorialHeadline)
                    .foregroundColor(.editorialText)

                Text(error)
                    .font(.editorialBody)
                    .foregroundColor(.editorialSub)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Button(action: onRetry) {
                Label("Try Again", systemImage: "arrow.clockwise")
                    .font(.subheadline.weight(.medium))
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
            .tint(.editorialSub)
            .padding(.top, 4)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
        .padding(.bottom, 200)
    }
}

// MARK: - Processing State

struct DiscoveryProcessingStateView: View {
    let runStatusDescription: String
    let currentJobStage: Int

    @State private var pulseScale: CGFloat = 1.0

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "sparkles")
                .font(.system(size: 32, weight: .light))
                .foregroundColor(.editorialSub)

            VStack(spacing: 8) {
                Text("Discovering New Content")
                    .font(.editorialHeadline)
                    .foregroundColor(.editorialText)

                Text(runStatusDescription)
                    .font(.editorialBody)
                    .foregroundColor(.editorialSub)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }

            // Progress dots
            HStack(spacing: 8) {
                ForEach(0..<4, id: \.self) { index in
                    Circle()
                        .fill(index <= currentJobStage ? Color.editorialText : Color.editorialBorder)
                        .frame(width: 6, height: 6)
                        .scaleEffect(index == currentJobStage ? pulseScale : 1.0)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
        .padding(.bottom, 200)
        .onAppear {
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                pulseScale = 1.6
            }
        }
    }
}

// MARK: - Empty State

struct DiscoveryEmptyStateView: View {
    let onGenerate: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "sparkles")
                .font(.system(size: 32, weight: .light))
                .foregroundColor(.editorialSub)

            VStack(spacing: 8) {
                Text("Discover New Content")
                    .font(.editorialHeadline)
                    .foregroundColor(.editorialText)

                Text("Get personalized suggestions for feeds, podcasts, and channels based on your reading history.")
                    .font(.editorialBody)
                    .foregroundColor(.editorialSub)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Button(action: onGenerate) {
                Label("Generate Suggestions", systemImage: "sparkles")
                    .font(.subheadline.weight(.medium))
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.regular)
            .padding(.top, 4)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
        .padding(.bottom, 200)
    }
}
