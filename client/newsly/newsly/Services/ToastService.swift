//
//  ToastService.swift
//  newsly
//
//  Toast notification service for app-wide messaging
//

import Foundation
import SwiftUI

enum ToastType {
    case success
    case error
    case info

    var icon: String {
        switch self {
        case .success: return "checkmark.circle.fill"
        case .error: return "exclamationmark.triangle.fill"
        case .info: return "info.circle.fill"
        }
    }

    var color: Color {
        switch self {
        case .success: return .green
        case .error: return .red
        case .info: return .blue
        }
    }
}

struct ToastMessage: Identifiable {
    let id = UUID()
    let message: String
    let type: ToastType
    let duration: TimeInterval

    init(message: String, type: ToastType, duration: TimeInterval = 3.0) {
        self.message = message
        self.type = type
        self.duration = duration
    }
}

@MainActor
class ToastService: ObservableObject {
    static let shared = ToastService()

    @Published var currentToast: ToastMessage?

    private init() {}

    func show(_ message: String, type: ToastType = .info, duration: TimeInterval = 3.0) {
        currentToast = ToastMessage(message: message, type: type, duration: duration)

        Task {
            try? await Task.sleep(nanoseconds: UInt64(duration * 1_000_000_000))
            if currentToast?.id == currentToast?.id {
                currentToast = nil
            }
        }
    }

    func showError(_ message: String) {
        show(message, type: .error)
    }

    func showSuccess(_ message: String) {
        show(message, type: .success)
    }
}
