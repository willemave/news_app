//
//  ContentRepository.swift
//  newsly
//
//  Created by Assistant on 3/16/26.
//

import Combine
import Foundation

protocol ContentRepositoryType {
    func loadPage(
        contentTypes: [ContentType],
        readFilter: ReadFilter,
        cursor: String?,
        limit: Int?
    ) -> AnyPublisher<ContentListResponse, Error>

    func loadDetail(id: Int) -> AnyPublisher<ContentDetail, Error>
}

final class ContentRepository: ContentRepositoryType {
    private let client: APIClient
    private let defaultPageSize: Int

    init(client: APIClient = .shared, defaultPageSize: Int = 25) {
        self.client = client
        self.defaultPageSize = defaultPageSize
    }

    func loadPage(
        contentTypes: [ContentType],
        readFilter: ReadFilter,
        cursor: String?,
        limit: Int? = nil
    ) -> AnyPublisher<ContentListResponse, Error> {
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "read_filter", value: readFilter.rawValue),
            URLQueryItem(name: "limit", value: String(limit ?? defaultPageSize))
        ]

        contentTypes.forEach { type in
            queryItems.append(URLQueryItem(name: "content_type", value: type.rawValue))
        }

        if let cursor {
            queryItems.append(URLQueryItem(name: "cursor", value: cursor))
        }

        return client.publisher(
            APIEndpoints.contentList,
            queryItems: queryItems
        )
    }

    func loadDetail(id: Int) -> AnyPublisher<ContentDetail, Error> {
        client.publisher(APIEndpoints.contentDetail(id: id))
    }
}
