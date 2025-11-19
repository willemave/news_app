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
        print("DEBUG: ScraperSettingsViewModel.loadConfigs() called")
        isLoading = true
        errorMessage = nil
        do {
            configs = try await service.listConfigs()
            print("DEBUG: Successfully loaded \(configs.count) scraper configs")
            for config in configs {
                print("DEBUG: Config: \(config.displayName ?? "N/A") (\(config.scraperType))")
            }
        } catch {
            print("DEBUG: Error loading scraper configs: \(error)")
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

    func updateConfig(_ config: ScraperConfig, isActive: Bool? = nil, displayName: String? = nil, feedURL: String? = nil) async {
        errorMessage = nil
        do {
            let updated = try await service.updateConfig(
                configId: config.id,
                displayName: displayName,
                feedURL: feedURL,
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
