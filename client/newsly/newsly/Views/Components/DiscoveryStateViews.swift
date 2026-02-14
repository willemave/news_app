//
//  DiscoveryStateViews.swift
//  newsly
//

import SwiftUI

struct DiscoveryLoadingStateView: View {
    var body: some View {
        VStack(spacing: 16) {
            ProgressView()

            Text("Loading...")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
        .padding(.bottom, 200)
    }
}

struct DiscoveryErrorStateView: View {
    let error: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 32, weight: .light))
                .foregroundColor(.secondary)

            VStack(spacing: 6) {
                Text("Something went wrong")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)

                Text(error)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Button(action: onRetry) {
                Text("Try Again")
                    .font(.subheadline)
                    .foregroundColor(.accentColor)
            }
            .padding(.top, 4)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
        .padding(.bottom, 200)
    }
}

struct DiscoveryProcessingStateView: View {
    let runStatusDescription: String
    let currentJobStage: Int

    var body: some View {
        VStack(spacing: 24) {
            ProgressView()

            VStack(spacing: 8) {
                Text("Discovering New Content")
                    .font(.title3)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)

                Text(runStatusDescription)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }

            HStack(spacing: 8) {
                ForEach(0..<4, id: \.self) { index in
                    Circle()
                        .fill(index <= currentJobStage ? Color.primary : Color(.tertiaryLabel))
                        .frame(width: 6, height: 6)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
        .padding(.bottom, 200)
    }
}

struct DiscoveryEmptyStateView: View {
    let onGenerate: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "sparkles")
                .font(.system(size: 40, weight: .light))
                .foregroundColor(.secondary)

            VStack(spacing: 8) {
                Text("Discover New Content")
                    .font(.title3)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)

                Text("AI-powered suggestions based on your reading history")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }

            Button(action: onGenerate) {
                Text("Generate Suggestions")
                    .font(.subheadline)
                    .foregroundColor(.accentColor)
            }
            .padding(.top, 8)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
        .padding(.bottom, 200)
    }
}

private struct DiscoveryRunningJobCard: View {
    let runStatusDescription: String
    let currentJobStage: Int

    var body: some View {
        VStack(spacing: 12) {
            HStack(spacing: 10) {
                ProgressView()

                VStack(alignment: .leading, spacing: 2) {
                    Text("Discovery in Progress")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)

                    Text(runStatusDescription)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()
            }

            HStack(spacing: 8) {
                ForEach(0..<4, id: \.self) { index in
                    Circle()
                        .fill(index <= currentJobStage ? Color.primary : Color(.tertiaryLabel))
                        .frame(width: 6, height: 6)
                }
            }
        }
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
        .padding(.horizontal, 20)
    }
}
