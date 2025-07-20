//
//  ContentSummary.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation

struct ContentSummary: Codable, Identifiable {
    let id: Int
    let contentType: String
    let url: String
    let title: String?
    let source: String?
    let status: String
    let shortSummary: String?
    let createdAt: String
    let processedAt: String?
    let classification: String?
    let publicationDate: String?
    let isRead: Bool
    
    enum CodingKeys: String, CodingKey {
        case id
        case contentType = "content_type"
        case url
        case title
        case source
        case status
        case shortSummary = "short_summary"
        case createdAt = "created_at"
        case processedAt = "processed_at"
        case classification
        case publicationDate = "publication_date"
        case isRead = "is_read"
    }
    
    var contentTypeEnum: ContentType? {
        ContentType(rawValue: contentType)
    }
    
    var displayTitle: String {
        title ?? "Untitled"
    }
    
    var formattedDate: String {
        let dateString = processedAt ?? createdAt
        
        // Debug logging
        print("DEBUG: Attempting to parse date string: '\(dateString)'")
        print("DEBUG: processedAt = \(processedAt ?? "nil"), createdAt = \(createdAt)")
        
        // Try multiple date formats
        var date: Date?
        
        // Try ISO8601 with fractional seconds
        let iso8601WithFractional = ISO8601DateFormatter()
        iso8601WithFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        date = iso8601WithFractional.date(from: dateString)
        if date != nil {
            print("DEBUG: Successfully parsed with ISO8601 fractional seconds")
        }
        
        // Try ISO8601 without fractional seconds
        if date == nil {
            let iso8601 = ISO8601DateFormatter()
            iso8601.formatOptions = [.withInternetDateTime]
            date = iso8601.date(from: dateString)
            if date != nil {
                print("DEBUG: Successfully parsed with ISO8601")
            }
        }
        
        // Try basic ISO format
        if date == nil {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
            formatter.timeZone = TimeZone(abbreviation: "UTC")
            date = formatter.date(from: dateString)
            if date != nil {
                print("DEBUG: Successfully parsed with microseconds format")
            }
        }
        
        // Try without microseconds
        if date == nil {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
            formatter.timeZone = TimeZone(abbreviation: "UTC")
            date = formatter.date(from: dateString)
            if date != nil {
                print("DEBUG: Successfully parsed with basic format")
            }
        }
        
        guard let date = date else { 
            print("DEBUG: Failed to parse date, returning 'Date unknown'")
            return "Date unknown" 
        }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        displayFormatter.timeZone = TimeZone.current
        return displayFormatter.string(from: date)
    }
}