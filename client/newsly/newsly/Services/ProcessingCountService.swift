//
//  ProcessingCountService.swift
//  newsly
//
//  Created by Assistant on 1/16/26.
//

import Combine
import Foundation

struct ProcessingCountResponse: Codable {
    let processingCount: Int

    enum CodingKeys: String, CodingKey {
        case processingCount = "processing_count"
    }
}

@MainActor
final class ProcessingCountService: ObservableObject {
    static let shared = ProcessingCountService()

    @Published var processingCount: Int = 0

    private let client = APIClient.shared
    private var refreshTimer: Timer?

    private init() {
        startPeriodicRefresh()
    }

    deinit {
        refreshTimer?.invalidate()
    }

    func refreshCount() async {
        do {
            let response: ProcessingCountResponse = try await client.request(APIEndpoints.processingCount)
            processingCount = response.processingCount
        } catch {
            print("Failed to fetch processing count: \(error)")
        }
    }

    private func startPeriodicRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { _ in
            Task {
                await self.refreshCount()
            }
        }
    }
}
