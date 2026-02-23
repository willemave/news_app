//
//  LaneStatusRow.swift
//  newsly
//
//  Extracted from OnboardingFlowView for reuse in DiscoveryPersonalizeSheet.
//

import SwiftUI

struct LaneStatusRow: View {
    let lane: OnboardingDiscoveryLaneStatus

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(statusColor.opacity(0.12))
                    .frame(width: 32, height: 32)
                Image(systemName: statusIcon)
                    .font(.caption.weight(.semibold))
                    .foregroundColor(statusColor)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(lane.name)
                    .font(.callout)
                    .foregroundColor(.watercolorSlate)
                Text(statusLabel)
                    .font(.caption)
                    .foregroundColor(.watercolorSlate.opacity(0.6))
            }
            Spacer()
        }
        .padding(.vertical, 4)
    }

    private var statusLabel: String {
        switch lane.status {
        case "processing": return "Searching..."
        case "completed": return "Done"
        case "failed": return "Failed"
        default: return "Queued"
        }
    }

    private var statusIcon: String {
        switch lane.status {
        case "processing": return "hourglass"
        case "completed": return "checkmark"
        case "failed": return "exclamationmark"
        default: return "circle"
        }
    }

    private var statusColor: Color {
        switch lane.status {
        case "processing": return .watercolorSlate
        case "completed": return .watercolorPaleEmerald
        case "failed": return .watercolorDiffusedPeach
        default: return .watercolorSlate.opacity(0.4)
        }
    }
}
