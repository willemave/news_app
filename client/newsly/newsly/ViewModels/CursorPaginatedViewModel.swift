//
//  CursorPaginatedViewModel.swift
//  newsly
//

import Foundation

@MainActor
class CursorPaginatedViewModel: ObservableObject {
    @Published var nextCursor: String?
    @Published var hasMore: Bool = false

    func resetPagination() {
        nextCursor = nil
        hasMore = false
    }

    func applyPagination(nextCursor: String?, hasMore: Bool) {
        self.nextCursor = nextCursor
        self.hasMore = hasMore
    }

    func applyPagination(_ response: ContentListResponse) {
        applyPagination(nextCursor: response.nextCursor, hasMore: response.hasMore)
    }
}

