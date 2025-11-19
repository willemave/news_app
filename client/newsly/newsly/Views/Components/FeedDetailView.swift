//
//  FeedDetailView.swift
//  newsly
//

import SwiftUI

struct FeedDetailView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var viewModel: ScraperSettingsViewModel
    let config: ScraperConfig

    @State private var displayName: String
    @State private var feedURL: String
    @State private var isActive: Bool
    @State private var showingDeleteAlert = false
    @State private var isSaving = false
    @State private var showingSaveSuccess = false

    init(viewModel: ScraperSettingsViewModel, config: ScraperConfig) {
        self.viewModel = viewModel
        self.config = config
        _displayName = State(initialValue: config.displayName ?? "")
        _feedURL = State(initialValue: config.feedURL ?? "")
        _isActive = State(initialValue: config.isActive)
    }

    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Feed Information")) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Type")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text(config.scraperType.capitalized)
                            .font(.body)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 4)
                }

                Section(header: Text("Settings")) {
                    Toggle("Active", isOn: $isActive)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("Display Name")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        TextField("Display Name", text: $displayName)
                            .textInputAutocapitalization(.words)
                    }
                    .padding(.vertical, 4)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("Feed URL")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        TextField("Feed URL", text: $feedURL)
                            .keyboardType(.URL)
                            .textInputAutocapitalization(.never)
                            .disableAutocorrection(true)
                    }
                    .padding(.vertical, 4)
                }

                if viewModel.errorMessage != nil {
                    Section {
                        HStack {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundColor(.red)
                            Text(viewModel.errorMessage ?? "")
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                    }
                }

                Section {
                    Button(role: .destructive) {
                        showingDeleteAlert = true
                    } label: {
                        HStack {
                            Spacer()
                            Label("Delete Feed", systemImage: "trash")
                            Spacer()
                        }
                    }
                }
            }
            .navigationTitle("Feed Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task { await saveChanges() }
                    } label: {
                        if isSaving {
                            ProgressView()
                        } else {
                            Text("Save")
                        }
                    }
                    .disabled(isSaving || !hasChanges || feedURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .alert("Delete Feed", isPresented: $showingDeleteAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Delete", role: .destructive) {
                    Task {
                        await viewModel.deleteConfig(config)
                        dismiss()
                    }
                }
            } message: {
                Text("Are you sure you want to delete this feed? This action cannot be undone.")
            }
            .overlay {
                if showingSaveSuccess {
                    VStack {
                        Spacer()
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                            Text("Saved successfully")
                                .foregroundColor(.primary)
                        }
                        .padding()
                        .background(Color(.systemBackground))
                        .cornerRadius(10)
                        .shadow(radius: 10)
                        .padding(.bottom, 50)
                    }
                    .transition(.move(edge: .bottom))
                }
            }
        }
    }

    private var hasChanges: Bool {
        displayName != (config.displayName ?? "") ||
        feedURL != (config.feedURL ?? "") ||
        isActive != config.isActive
    }

    private func saveChanges() async {
        isSaving = true
        defer { isSaving = false }

        await viewModel.updateConfig(
            config,
            isActive: isActive != config.isActive ? isActive : nil,
            displayName: displayName != (config.displayName ?? "") ? displayName : nil,
            feedURL: feedURL != (config.feedURL ?? "") ? feedURL : nil
        )

        if viewModel.errorMessage == nil {
            withAnimation {
                showingSaveSuccess = true
            }

            try? await Task.sleep(nanoseconds: 1_500_000_000)

            withAnimation {
                showingSaveSuccess = false
            }

            try? await Task.sleep(nanoseconds: 300_000_000)
            dismiss()
        }
    }

    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        guard let date = formatter.date(from: dateString) else {
            return dateString
        }

        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        return displayFormatter.string(from: date)
    }
}
