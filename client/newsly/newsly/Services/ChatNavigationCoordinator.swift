//
//  ChatNavigationCoordinator.swift
//  newsly
//
//  Created by Assistant on 4/6/26.
//

import Foundation

@MainActor
final class ChatNavigationCoordinator: ObservableObject {
    static let shared = ChatNavigationCoordinator()

    @Published private(set) var pendingRoute: ChatSessionRoute?

    private init() {}

    func open(_ route: ChatSessionRoute) {
        pendingRoute = route
    }

    func clear(route: ChatSessionRoute? = nil) {
        guard let route else {
            pendingRoute = nil
            return
        }

        if pendingRoute == route {
            pendingRoute = nil
        }
    }
}
