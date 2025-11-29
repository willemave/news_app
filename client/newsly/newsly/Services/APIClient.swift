//
//  APIClient.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Combine
import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "APIClient")

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

        // Ensure we send a token or attempt refresh before issuing the request
        if let accessToken = try await fetchAccessTokenOrRefresh() {
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

            // Handle 401/403 (missing or expired token) - try refresh once
            if httpResponse.statusCode == 401 || httpResponse.statusCode == 403 {
                do {
                    _ = try await AuthenticationService.shared.refreshAccessToken()
                    // Retry request with new token
                    return try await self.request(endpoint, method: method, body: body, queryItems: queryItems)
                } catch let authError as AuthError {
                    switch authError {
                    case .refreshTokenExpired, .noRefreshToken:
                        NotificationCenter.default.post(name: .authenticationRequired, object: nil)
                        throw APIError.unauthorized
                    default:
                        throw APIError.networkError(authError)
                    }
                } catch {
                    throw APIError.networkError(error)
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

        // Ensure we send a token or attempt refresh before issuing the request
        if let accessToken = try await fetchAccessTokenOrRefresh() {
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

            // Handle 401/403 (missing or expired token) - try refresh once
            if httpResponse.statusCode == 401 || httpResponse.statusCode == 403 {
                do {
                    _ = try await AuthenticationService.shared.refreshAccessToken()
                    return try await self.requestVoid(endpoint, method: method, body: body)
                } catch let authError as AuthError {
                    switch authError {
                    case .refreshTokenExpired, .noRefreshToken:
                        NotificationCenter.default.post(name: .authenticationRequired, object: nil)
                        throw APIError.unauthorized
                    default:
                        throw APIError.networkError(authError)
                    }
                } catch {
                    throw APIError.networkError(error)
                }
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                logger.error("[APIClient] HTTP error | endpoint=\(endpoint, privacy: .public) status=\(httpResponse.statusCode)")
                throw APIError.httpError(statusCode: httpResponse.statusCode)
            }
        } catch let error as APIError {
            throw error
        } catch {
            logger.error("[APIClient] Network error | endpoint=\(endpoint, privacy: .public) error=\(error.localizedDescription)")
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

        // Ensure we send a token or attempt refresh before issuing the request
        if let accessToken = try await fetchAccessTokenOrRefresh() {
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

            // Handle 401/403 (missing or expired token) - try refresh once
            if httpResponse.statusCode == 401 || httpResponse.statusCode == 403 {
                do {
                    _ = try await AuthenticationService.shared.refreshAccessToken()
                    // Retry request with new token
                    return try await self.requestRaw(endpoint, method: method, body: body, queryItems: queryItems)
                } catch let authError as AuthError {
                    switch authError {
                    case .refreshTokenExpired, .noRefreshToken:
                        NotificationCenter.default.post(name: .authenticationRequired, object: nil)
                        throw APIError.unauthorized
                    default:
                        throw APIError.networkError(authError)
                    }
                } catch {
                    throw APIError.networkError(error)
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

    /// Stream NDJSON responses line by line
    func streamNDJSON<T: Decodable>(
        _ endpoint: String,
        method: String = "POST",
        body: Data? = nil
    ) -> AsyncThrowingStream<T, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    guard let url = URL(string: AppSettings.shared.baseURL + endpoint) else {
                        logger.error("[Stream] Invalid URL | endpoint=\(endpoint, privacy: .public)")
                        continuation.finish(throwing: APIError.invalidURL)
                        return
                    }

                    var request = URLRequest(url: url)
                    request.httpMethod = method
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("application/x-ndjson", forHTTPHeaderField: "Accept")

                    if let accessToken = try await fetchAccessTokenOrRefresh() {
                        request.addValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
                    }

                    if let body = body {
                        request.httpBody = body
                    }

                    let (bytes, response) = try await session.bytes(for: request)

                    guard let httpResponse = response as? HTTPURLResponse else {
                        continuation.finish(throwing: APIError.unknown)
                        return
                    }

                    guard (200...299).contains(httpResponse.statusCode) else {
                        if httpResponse.statusCode == 401 || httpResponse.statusCode == 403 {
                            continuation.finish(throwing: APIError.unauthorized)
                        } else {
                            logger.error("[Stream] HTTP error | endpoint=\(endpoint, privacy: .public) status=\(httpResponse.statusCode)")
                            continuation.finish(throwing: APIError.httpError(statusCode: httpResponse.statusCode))
                        }
                        return
                    }

                    for try await line in bytes.lines {
                        guard !line.isEmpty else { continue }

                        guard let lineData = line.data(using: .utf8) else { continue }

                        do {
                            let decoded = try self.decoder.decode(T.self, from: lineData)
                            continuation.yield(decoded)
                        } catch {
                            logger.debug("[Stream] Decode error: \(error.localizedDescription, privacy: .public)")
                        }
                    }

                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish()
                } catch {
                    logger.error("[Stream] Error | endpoint=\(endpoint, privacy: .public) error=\(error.localizedDescription, privacy: .public)")
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    /// Get an access token if present; otherwise attempt a refresh.
    /// Returns nil for truly unauthenticated flows (e.g., public endpoints).
    private func fetchAccessTokenOrRefresh() async throws -> String? {
        if let token = KeychainManager.shared.getToken(key: .accessToken) {
            return token
        }

        // If we have a refresh token, attempt to refresh and return the new access token.
        guard KeychainManager.shared.getToken(key: .refreshToken) != nil else {
            return nil
        }

        do {
            let refreshed = try await AuthenticationService.shared.refreshAccessToken()
            return refreshed
        } catch let authError as AuthError {
            switch authError {
            case .refreshTokenExpired, .noRefreshToken:
                NotificationCenter.default.post(name: .authenticationRequired, object: nil)
                throw APIError.unauthorized
            default:
                throw APIError.networkError(authError)
            }
        } catch {
            throw APIError.networkError(error)
        }
    }
}

// MARK: - Notification Extensions

extension Notification.Name {
    static let authenticationRequired = Notification.Name("authenticationRequired")
}

// MARK: - Combine bridge

extension APIClient {
    func publisher<T: Decodable>(
        _ endpoint: String,
        method: String = "GET",
        body: Data? = nil,
        queryItems: [URLQueryItem]? = nil
    ) -> AnyPublisher<T, Error> {
        Deferred {
            Future { promise in
                Task {
                    do {
                        let result: T = try await self.request(
                            endpoint,
                            method: method,
                            body: body,
                            queryItems: queryItems
                        )
                        promise(.success(result))
                    } catch {
                        promise(.failure(error))
                    }
                }
            }
        }
        .eraseToAnyPublisher()
    }

    func publisherVoid(
        _ endpoint: String,
        method: String = "POST",
        body: Data? = nil
    ) -> AnyPublisher<Void, Error> {
        Deferred {
            Future { promise in
                Task {
                    do {
                        try await self.requestVoid(endpoint, method: method, body: body)
                        promise(.success(()))
                    } catch {
                        promise(.failure(error))
                    }
                }
            }
        }
        .eraseToAnyPublisher()
    }
}
