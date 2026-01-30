//
//  SourceDetailSheet.swift
//  newsly
//
//  Detail sheet for editing feed/podcast sources.
//

import SwiftUI

struct SourceDetailSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var viewModel: ScraperSettingsViewModel
    let config: ScraperConfig

    @State private var displayName: String
    @State private var feedURL: String
    @State private var isActive: Bool
    @State private var limit: String
    @State private var showingDeleteAlert = false
    @State private var isSaving = false

    init(viewModel: ScraperSettingsViewModel, config: ScraperConfig) {
        self.viewModel = viewModel
        self.config = config
        _displayName = State(initialValue: config.displayName ?? "")
        _feedURL = State(initialValue: config.feedURL ?? "")
        _isActive = State(initialValue: config.isActive)
        _limit = State(initialValue: config.limit.map(String.init) ?? "")
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Info card
                    infoCard

                    // Settings card
                    settingsCard

                    // Error message
                    if let error = viewModel.errorMessage {
                        errorBanner(error)
                    }

                    // Delete button
                    deleteButton

                    Spacer(minLength: 40)
                }
                .padding()
            }
            .background(Color.surfacePrimary)
            .navigationTitle("Source Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    saveButton
                }
            }
            .alert("Delete Source", isPresented: $showingDeleteAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Delete", role: .destructive) {
                    Task {
                        await viewModel.deleteConfig(config)
                        dismiss()
                    }
                }
            } message: {
                Text("Are you sure you want to delete this source? This action cannot be undone.")
            }
        }
    }

    // MARK: - Info Card

    private var infoCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("INFORMATION")
                .font(.sectionHeader)
                .foregroundStyle(Color.textTertiary)
                .tracking(0.5)

            HStack {
                Text("Type")
                    .font(.listTitle)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                HStack(spacing: 6) {
                    SourceTypeIcon(type: config.scraperType)
                    Text(config.scraperType.capitalized)
                        .font(.listMono)
                        .foregroundStyle(Color.textSecondary)
                }
            }
        }
        .padding()
        .background(Color.surfaceSecondary, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Settings Card

    private var settingsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("SETTINGS")
                .font(.sectionHeader)
                .foregroundStyle(Color.textTertiary)
                .tracking(0.5)

            // Active toggle
            HStack {
                Text("Active")
                    .font(.listTitle)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Toggle("", isOn: $isActive)
                    .labelsHidden()
            }

            Divider()

            // Display name
            VStack(alignment: .leading, spacing: 6) {
                Text("Display Name")
                    .font(.listCaption)
                    .foregroundStyle(Color.textTertiary)

                TextField("Display Name", text: $displayName)
                    .textFieldStyle(.roundedBorder)
            }

            // Feed URL
            VStack(alignment: .leading, spacing: 6) {
                Text("Feed URL")
                    .font(.listCaption)
                    .foregroundStyle(Color.textTertiary)

                TextField("Feed URL", text: $feedURL)
                    .textFieldStyle(.roundedBorder)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            }

            // Limit (podcasts only)
            if config.scraperType == "podcast_rss" {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Episode Limit (1-100)")
                        .font(.listCaption)
                        .foregroundStyle(Color.textTertiary)

                    TextField("Optional", text: $limit)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                }
            }
        }
        .padding()
        .background(Color.surfaceSecondary, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Error Banner

    private func errorBanner(_ error: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(Color.statusDestructive)

            Text(error)
                .font(.subheadline)
                .foregroundStyle(Color.textPrimary)

            Spacer()
        }
        .padding()
        .background(Color.statusDestructive.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Delete Button

    private var deleteButton: some View {
        Button(role: .destructive) {
            showingDeleteAlert = true
        } label: {
            HStack {
                Spacer()
                Label("Delete Source", systemImage: "trash")
                    .font(.body.weight(.medium))
                Spacer()
            }
            .padding(.vertical, 12)
        }
        .buttonStyle(.bordered)
        .tint(.red)
    }

    // MARK: - Save Button

    private var saveButton: some View {
        Button {
            Task { await saveChanges() }
        } label: {
            if isSaving {
                ProgressView()
            } else {
                Text("Save")
                    .fontWeight(.semibold)
            }
        }
        .disabled(isSaving || !hasChanges || feedURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !limitIsValid)
    }

    // MARK: - Helpers

    private var hasChanges: Bool {
        displayName != (config.displayName ?? "") ||
        feedURL != (config.feedURL ?? "") ||
        isActive != config.isActive ||
        (config.scraperType == "podcast_rss" && normalizedLimit != config.limit)
    }

    private var normalizedLimit: Int? {
        let trimmed = limit.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return Int(trimmed)
    }

    private var limitIsValid: Bool {
        guard config.scraperType == "podcast_rss" else { return true }
        guard let value = normalizedLimit else { return true }
        return (1...100).contains(value)
    }

    private func saveChanges() async {
        isSaving = true
        defer { isSaving = false }

        await viewModel.updateConfig(
            config,
            isActive: isActive != config.isActive ? isActive : nil,
            displayName: displayName != (config.displayName ?? "") ? displayName : nil,
            feedURL: feedURL != (config.feedURL ?? "") ? feedURL : nil,
            limit: (config.scraperType == "podcast_rss" && normalizedLimit != config.limit) ? normalizedLimit : nil
        )

        if viewModel.errorMessage == nil {
            dismiss()
        }
    }
}
