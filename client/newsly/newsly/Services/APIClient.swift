//
//  APIClient.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case noData
    case decodingError(Error)
    case networkError(Error)
    case httpError(statusCode: Int)
    case unauthorized
    case unknown

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .noData:
            return "No data received"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .httpError(let statusCode):
            return "HTTP error: \(statusCode)"
        case .unauthorized:
            return "Unauthorized - please sign in again"
        case .unknown:
            return "An unknown error occurred"
        }
    }
}

class APIClient {
    static let shared = APIClient()
    private let session: URLSession
    private let decoder: JSONDecoder
    
    private init() {
        self.session = URLSession.shared
        self.decoder = JSONDecoder()
    }
    
    func request<T: Decodable>(_ endpoint: String,
                               method: String = "GET",
                               body: Data? = nil,
                               queryItems: [URLQueryItem]? = nil) async throws -> T {
        guard var components = URLComponents(string: AppSettings.shared.baseURL + endpoint) else {
            throw APIError.invalidURL
        }

        if let queryItems = queryItems {
            components.queryItems = queryItems
        }

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Add Bearer token if available
        if let accessToken = KeychainManager.shared.getToken(key: .accessToken) {
            request.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = body
        }

        do {
            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.unknown
            }

            // Handle 401 - token expired, try refresh
            if httpResponse.statusCode == 401 {
                do {
                    _ = try await AuthenticationService.shared.refreshAccessToken()
                    // Retry request with new token
                    return try await self.request(endpoint, method: method, body: body, queryItems: queryItems)
                } catch {
                    // Refresh failed - logout user
                    NotificationCenter.default.post(name: .authenticationRequired, object: nil)
                    throw APIError.unauthorized
                }
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.httpError(statusCode: httpResponse.statusCode)
            }

            do {
                return try decoder.decode(T.self, from: data)
            } catch {
                throw APIError.decodingError(error)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.networkError(error)
        }
    }
    
    func requestVoid(_ endpoint: String,
                     method: String = "POST",
                     body: Data? = nil) async throws {
        guard let url = URL(string: AppSettings.shared.baseURL + endpoint) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Add Bearer token if available
        if let accessToken = KeychainManager.shared.getToken(key: .accessToken) {
            request.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = body
        }

        do {
            let (_, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.unknown
            }

            // Handle 401 - token expired, try refresh
            if httpResponse.statusCode == 401 {
                do {
                    _ = try await AuthenticationService.shared.refreshAccessToken()
                    // Retry request with new token
                    return try await self.requestVoid(endpoint, method: method, body: body)
                } catch {
                    // Refresh failed - logout user
                    NotificationCenter.default.post(name: .authenticationRequired, object: nil)
                    throw APIError.unauthorized
                }
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.httpError(statusCode: httpResponse.statusCode)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.networkError(error)
        }
    }
    
    func requestRaw(_ endpoint: String,
                    method: String = "GET",
                    body: Data? = nil,
                    queryItems: [URLQueryItem]? = nil) async throws -> [String: Any] {
        guard var components = URLComponents(string: AppSettings.shared.baseURL + endpoint) else {
            throw APIError.invalidURL
        }

        if let queryItems = queryItems {
            components.queryItems = queryItems
        }

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Add Bearer token if available
        if let accessToken = KeychainManager.shared.getToken(key: .accessToken) {
            request.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = body
        }

        do {
            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.unknown
            }

            // Handle 401 - token expired, try refresh
            if httpResponse.statusCode == 401 {
                do {
                    _ = try await AuthenticationService.shared.refreshAccessToken()
                    // Retry request with new token
                    return try await self.requestRaw(endpoint, method: method, body: body, queryItems: queryItems)
                } catch {
                    // Refresh failed - logout user
                    NotificationCenter.default.post(name: .authenticationRequired, object: nil)
                    throw APIError.unauthorized
                }
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.httpError(statusCode: httpResponse.statusCode)
            }

            guard let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any] else {
                throw APIError.decodingError(NSError(domain: "APIClient", code: 0, userInfo: [NSLocalizedDescriptionKey: "Invalid JSON response"]))
            }

            return json
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.networkError(error)
        }
    }
}

// MARK: - Notification Extensions

extension Notification.Name {
    static let authenticationRequired = Notification.Name("authenticationRequired")
}