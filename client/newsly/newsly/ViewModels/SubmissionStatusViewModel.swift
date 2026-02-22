//
//  SubmissionStatusViewModel.swift
//  newsly
//
//  Created by Assistant on 1/14/26.
//

import Foundation
import os.log

private let logger = Logger(subsystem: "com.newsly", category: "SubmissionStatusViewModel")

@MainActor
final class SubmissionStatusViewModel: CursorPaginatedViewModel {
    @Published var submissions: [SubmissionStatusItem] = []
    @Published var isLoading = false
    @Published var isLoadingMore = false
    @Published var errorMessage: String?

    func load() async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let response = try await ContentService.shared.fetchSubmissionStatusList()
            submissions = response.submissions
            applyPagination(nextCursor: response.nextCursor, hasMore: response.hasMore)
        } catch {
            logger.error("[SubmissionStatusViewModel] load failed | error=\(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }
    }

    func loadMore() async {
        guard !isLoadingMore, hasMore, let cursor = nextCursor else { return }
        isLoadingMore = true
        defer { isLoadingMore = false }

        do {
            let response = try await ContentService.shared.fetchSubmissionStatusList(cursor: cursor)
            submissions.append(contentsOf: response.submissions)
            applyPagination(nextCursor: response.nextCursor, hasMore: response.hasMore)
        } catch {
            logger.error("[SubmissionStatusViewModel] loadMore failed | error=\(error.localizedDescription)")
        }
    }
}
