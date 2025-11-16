//
//  ScraperSettingsViewModel.swift
//  newsly
//

import Foundation

@MainActor
class ScraperSettingsViewModel: ObservableObject {
    @Published var configs: [ScraperConfig] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    private let service = ScraperConfigService.shared

    func loadConfigs() async {
        isLoading = true
        errorMessage = nil
        do {
            configs = try await service.listConfigs()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func addConfig(scraperType: String, displayName: String?, feedURL: String) async {
        errorMessage = nil
        do {
            let newConfig = try await service.createConfig(
                scraperType: scraperType,
                displayName: displayName,
                feedURL: feedURL,
                isActive: true
            )
            configs.insert(newConfig, at: 0)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func updateConfig(_ config: ScraperConfig, isActive: Bool? = nil, displayName: String? = nil) async {
        errorMessage = nil
        do {
            let updated = try await service.updateConfig(
                configId: config.id,
                displayName: displayName,
                feedURL: nil,
                isActive: isActive
            )
            if let index = configs.firstIndex(where: { $0.id == updated.id }) {
                configs[index] = updated
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deleteConfig(_ config: ScraperConfig) async {
        errorMessage = nil
        do {
            try await service.deleteConfig(configId: config.id)
            configs.removeAll { $0.id == config.id }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
