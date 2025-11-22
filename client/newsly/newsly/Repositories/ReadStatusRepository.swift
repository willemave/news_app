//
//  ReadStatusRepository.swift
//  newsly
//
//  Created by Assistant on 3/16/26.
//

import Combine
import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "ReadStatus")

protocol ReadStatusRepositoryType {
    func markRead(ids: [Int]) -> AnyPublisher<Void, Error>
}

final class ReadStatusRepository: ReadStatusRepositoryType {
    private let client: APIClient
    private let encoder = JSONEncoder()

    init(client: APIClient = .shared) {
        self.client = client
    }

    func markRead(ids: [Int]) -> AnyPublisher<Void, Error> {
        guard !ids.isEmpty else {
            logger.debug("[ReadStatus] markRead called with empty ids, skipping")
            return Just(())
                .setFailureType(to: Error.self)
                .eraseToAnyPublisher()
        }

        logger.info("[ReadStatus] markRead called | ids=\(ids, privacy: .public) count=\(ids.count)")

        struct BulkMarkReadRequest: Codable {
            let contentIds: [Int]

            enum CodingKeys: String, CodingKey {
                case contentIds = "content_ids"
            }
        }

        let payload = BulkMarkReadRequest(contentIds: ids)
        let body = try? encoder.encode(payload)

        return client.publisher(
            APIEndpoints.bulkMarkRead,
            method: "POST",
            body: body
        )
        .handleEvents(
            receiveOutput: { _ in
                logger.info("[ReadStatus] markRead success | ids=\(ids, privacy: .public)")
            },
            receiveCompletion: { completion in
                if case .failure(let error) = completion {
                    logger.error("[ReadStatus] markRead failed | ids=\(ids, privacy: .public) error=\(error.localizedDescription)")
                }
            }
        )
        .map { (_: BulkMarkReadResponse) in () }
        .eraseToAnyPublisher()
    }
}
