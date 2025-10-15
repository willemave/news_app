//
//  NewsGroup.swift
//  newsly
//
//  Created by Assistant on 10/12/25.
//

import Foundation

/// Represents a group of 6 news items displayed together
struct NewsGroup: Identifiable {
    let id: String
    let items: [ContentSummary]
    var isRead: Bool

    init(items: [ContentSummary]) {
        // Use the first item's ID as the group ID
        self.id = items.first.map { "\($0.id)" } ?? UUID().uuidString
        self.items = items
        // Group is read if ALL items are read
        self.isRead = items.allSatisfy { $0.isRead }
    }

    /// Update read status for all items in group
    func updatingAllAsRead(_ read: Bool) -> NewsGroup {
        let updatedItems = items.map { $0.updating(isRead: read) }
        return NewsGroup(items: updatedItems)
    }

    /// Update a single item in the group
    func updatingItem(id: Int, with updater: (ContentSummary) -> ContentSummary) -> NewsGroup {
        let updatedItems = items.map { item in
            item.id == id ? updater(item) : item
        }
        return NewsGroup(items: updatedItems)
    }
}

extension Array where Element == ContentSummary {
    /// Group news items into groups of 6
    func groupedBySix() -> [NewsGroup] {
        var groups: [NewsGroup] = []
        for index in stride(from: 0, to: count, by: 6) {
            let endIndex = Swift.min(index + 6, count)
            let groupItems = Array(self[index..<endIndex])
            groups.append(NewsGroup(items: groupItems))
        }
        return groups
    }
}
