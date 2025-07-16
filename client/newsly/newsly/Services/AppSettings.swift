//
//  AppSettings.swift
//  newsly
//
//  Created by Assistant on 7/9/25.
//

import Foundation
import SwiftUI

class AppSettings: ObservableObject {
    static let shared = AppSettings()
    
    @AppStorage("serverHost") var serverHost: String = "localhost"
    @AppStorage("serverPort") var serverPort: String = "8000"
    @AppStorage("useHTTPS") var useHTTPS: Bool = false
    
    var baseURL: String {
        let scheme = useHTTPS ? "https" : "http"
        return "\(scheme)://\(serverHost):\(serverPort)"
    }
    
    private init() {}
}