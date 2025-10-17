//
//  StructuredSummaryView.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI

struct StructuredSummaryView: View {
    let summary: StructuredSummary
    @State private var isKeyPointsExpanded = true
    @State private var isQuestionsExpanded = false
    @State private var isCounterArgsExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            // Key Points Section (expanded by default)
            if !summary.bulletPoints.isEmpty {
                DisclosureGroup(isExpanded: $isKeyPointsExpanded) {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(summary.bulletPoints, id: \.text) { point in
                            HStack(alignment: .top, spacing: 12) {
                                Circle()
                                    .fill(Color.accentColor)
                                    .frame(width: 6, height: 6)
                                    .padding(.top, 7)

                                VStack(alignment: .leading, spacing: 4) {
                                    Text(point.text)
                                        .font(.body)
                                        .fixedSize(horizontal: false, vertical: true)

                                    if let category = point.category {
                                        Text(category.replacingOccurrences(of: "_", with: " ").capitalized)
                                            .font(.caption)
                                            .foregroundColor(categoryColor(for: category))
                                            .fontWeight(.medium)
                                    }
                                }
                            }
                        }
                    }
                    .padding(.top, 12)
                } label: {
                    Text("Key Points")
                        .font(.title3)
                        .fontWeight(.semibold)
                }
                .tint(.primary)
            }

            // Questions Section
            if !(summary.questions ?? []).isEmpty {
                DisclosureGroup(isExpanded: $isQuestionsExpanded) {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(Array((summary.questions ?? []).enumerated()), id: \.offset) { index, question in
                            HStack(alignment: .top, spacing: 12) {
                                Text("\(index + 1)")
                                    .font(.body)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.accentColor)
                                    .frame(width: 24, alignment: .trailing)

                                Text(question)
                                    .font(.body)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .padding(.top, 12)
                } label: {
                    Text("Questions to Ask")
                        .font(.title3)
                        .fontWeight(.semibold)
                }
                .tint(.primary)
            }

            // Counter Arguments Section
            if !(summary.counterArguments ?? []).isEmpty {
                DisclosureGroup(isExpanded: $isCounterArgsExpanded) {
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(summary.counterArguments ?? [], id: \.self) { argument in
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.body)
                                    .foregroundColor(.orange)
                                    .frame(width: 20)

                                Text(argument)
                                    .font(.body)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .padding(.top, 12)
                } label: {
                    Text("Counter Arguments")
                        .font(.title3)
                        .fontWeight(.semibold)
                }
                .tint(.primary)
            }

            if !summary.quotes.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Notable Quotes")
                        .font(.title3)
                        .fontWeight(.semibold)

                    ForEach(summary.quotes, id: \.text) { quote in
                        VStack(alignment: .leading, spacing: 8) {
                            HStack(alignment: .top, spacing: 0) {
                                Text(quote.text)
                                    .font(.body)
                                    .italic()
                                    .fixedSize(horizontal: false, vertical: true)
                            }

                            if let context = quote.context {
                                Text("— \(context)")
                                    .font(.callout)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding(.leading, 16)
                        .overlay(
                            Rectangle()
                                .fill(Color.accentColor)
                                .frame(width: 3),
                            alignment: .leading
                        )
                    }
                }
            }

            if !summary.topics.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Topics")
                        .font(.title3)
                        .fontWeight(.semibold)

                    FlowLayout(spacing: 8) {
                        ForEach(summary.topics, id: \.self) { topic in
                            Text(topic)
                                .font(.subheadline)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(Color.accentColor.opacity(0.15))
                                .foregroundColor(.accentColor)
                                .clipShape(Capsule())
                        }
                    }
                }
            }
        }
    }

    // Helper function for category colors
    private func categoryColor(for category: String) -> Color {
        switch category.lowercased() {
        case "key_finding":
            return .green
        case "warning":
            return .red
        case "recommendation":
            return .blue
        default:
            return .gray
        }
    }
}

// Simple flow layout for topics
struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = FlowResult(
            in: proposal.replacingUnspecifiedDimensions().width,
            subviews: subviews,
            spacing: spacing
        )
        return result.bounds
    }
    
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = FlowResult(
            in: bounds.width,
            subviews: subviews,
            spacing: spacing
        )
        for row in result.rows {
            for (frameIndex, subviewIndex) in row.indices.enumerated() {
                let frame = row.frames[frameIndex]
                let position = CGPoint(
                    x: bounds.minX + frame.minX,
                    y: bounds.minY + frame.minY
                )
                subviews[subviewIndex].place(at: position, proposal: ProposedViewSize(frame.size))
            }
        }
    }
    
    struct FlowResult {
        var bounds = CGSize.zero
        var rows = [Row]()
        
        struct Row {
            var indices: Range<Int>
            var frames: [CGRect]
        }
        
        init(in maxPossibleWidth: CGFloat, subviews: Subviews, spacing: CGFloat) {
            var itemsInRow = 0
            var remainingWidth = maxPossibleWidth.isFinite ? maxPossibleWidth : .greatestFiniteMagnitude
            var rowMinY: CGFloat = 0.0
            var rowHeight: CGFloat = 0.0
            var rows = [Row]()
            
            for (index, subview) in zip(subviews.indices, subviews) {
                let idealSize = subview.sizeThatFits(.unspecified)
                if index != 0 && widthInRow(index: index, idealWidth: idealSize.width, spacing: spacing) > remainingWidth {
                    finalizeRow(indices: index - itemsInRow..<index, y: rowMinY, rows: &rows)
                    
                    bounds.width = max(bounds.width, maxPossibleWidth - remainingWidth)
                    rowMinY += rowHeight + spacing
                    itemsInRow = 0
                    remainingWidth = maxPossibleWidth
                    rowHeight = 0
                }
                
                addToRow(index: index, idealSize: idealSize, spacing: spacing, &remainingWidth, &rowHeight)
                
                itemsInRow += 1
            }
            
            if itemsInRow > 0 {
                finalizeRow(indices: subviews.count - itemsInRow..<subviews.count, y: rowMinY, rows: &rows)
                bounds.width = max(bounds.width, maxPossibleWidth - remainingWidth)
            }
            
            bounds.height = rowMinY + rowHeight
            self.rows = rows
            
            func widthInRow(index: Int, idealWidth: CGFloat, spacing: CGFloat) -> CGFloat {
                idealWidth + (index == 0 ? 0 : spacing)
            }
            
            func addToRow(index: Int, idealSize: CGSize, spacing: CGFloat, _ remainingWidth: inout CGFloat, _ rowHeight: inout CGFloat) {
                let width = widthInRow(index: index, idealWidth: idealSize.width, spacing: spacing)
                
                remainingWidth -= width
                rowHeight = max(rowHeight, idealSize.height)
            }
            
            func finalizeRow(indices: Range<Int>, y: CGFloat, rows: inout [Row]) {
                var frames = [CGRect]()
                var x = 0.0
                for index in indices {
                    let idealSize = subviews[index].sizeThatFits(.unspecified)
                    let width = idealSize.width
                    let height = idealSize.height
                    frames.append(CGRect(x: x, y: y, width: width, height: height))
                    x += width + spacing
                }
                rows.append(Row(indices: indices, frames: frames))
            }
        }
    }
}

#Preview {
    StructuredSummaryView(summary: StructuredSummary(
        title: "Sample Title",
        overview: "This is a sample overview",
        bulletPoints: [
            BulletPoint(text: "Point 1", category: "key_finding"),
            BulletPoint(text: "Point 2", category: nil)
        ],
        quotes: [
            Quote(text: "Sample quote", context: "John Doe")
        ],
        topics: ["Topic 1", "Topic 2"],
        questions: [
            "What are the implications of this approach?",
            "How might this affect existing systems?"
        ],
        counterArguments: [
            "Some critics argue that this approach is too complex",
            "Alternative methods might be more efficient"
        ],
        summarizationDate: nil,
        classification: "to_read"
    ))
    .padding()
}