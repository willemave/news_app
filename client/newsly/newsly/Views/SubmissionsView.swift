//
//  SubmissionsView.swift
//  newsly
//
//  Created by Assistant on 1/15/26.
//

import SwiftUI

struct SubmissionsView: View {
    @ObservedObject var viewModel: SubmissionStatusViewModel

    var body: some View {
        Group {
            if viewModel.isLoading && viewModel.submissions.isEmpty {
                LoadingView()
            } else if let error = viewModel.errorMessage, viewModel.submissions.isEmpty {
                ErrorView(message: error) {
                    Task { await viewModel.load() }
                }
            } else if viewModel.submissions.isEmpty {
                emptyStateView
            } else {
                listView
            }
        }
        .navigationTitle("Submissions")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await viewModel.load()
        }
    }

    private var listView: some View {
        List {
            ForEach(viewModel.submissions) { submission in
                ZStack {
                    NavigationLink {
                        SubmissionDetailView(submission: submission)
                    } label: {
                        EmptyView()
                    }
                    .opacity(0)
                    .buttonStyle(PlainButtonStyle())

                    SubmissionStatusRow(submission: submission)
                }
                .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
                .onAppear {
                    if submission.id == viewModel.submissions.last?.id {
                        Task { await viewModel.loadMore() }
                    }
                }
            }

            if viewModel.isLoadingMore {
                HStack {
                    Spacer()
                    ProgressView()
                        .padding()
                    Spacer()
                }
                .listRowInsets(EdgeInsets())
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
            }
        }
        .listStyle(.plain)
        .refreshable {
            await viewModel.load()
        }
    }

    private var emptyStateView: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "tray")
                .font(.largeTitle)
                .foregroundColor(.secondary)
            Text("No submissions in progress.")
                .foregroundColor(.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(UIColor.systemBackground))
    }
}

#Preview {
    NavigationView {
        SubmissionsView(viewModel: SubmissionStatusViewModel())
    }
}
